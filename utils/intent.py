import json
import asyncio
from typing import Dict, Any
import logging

from utils.screening import screen_message
from utils.common import append_to_history
from utils.openai_client import get_client, build_responses_messages
from functions.notes import get_notes
from functions.videos import get_videos
from utils.common import user_conversations


async def classify_intent(query: str, user_id: int, sh: Any = None) -> Dict[str, Any]:
    """
    Basic intent classification using OpenAI Responses API.
    
    Returns a dict with keys: output_screener, output_intent, output_entitites, final_output
    """
    output: Dict[str, Any] = {
        "output_screener": "",
        "output_intent": "",
        "output_entitites": "",
        "final_output": "",
    }

    try:
        # Screen message for appropriateness
        screening = await screen_message(query)
        is_valid = bool(screening.get("is_valid", False))
        output["output_screener"] = is_valid
        if not is_valid:
            output["final_output"] = "Please use respectful language. [Warning]"
            return output

        # Get conversation history first
        history = user_conversations.get(user_id, [])
        
        # Enhanced system prompt with conversation context
        recent_context = ""
        if len(history) > 0:
            last_user_msg = next((m for m in reversed(history) if m.get("role") == "user"), None)
            last_assistant_msg = next((m for m in reversed(history) if m.get("role") == "assistant"), None)
            if last_assistant_msg and "specify:" in last_assistant_msg.get("content", ""):
                recent_context = f"\n\nCONTEXT: User was just asked to specify missing info. Current user message is likely providing that missing information."

        system_prompt = (
            "You are a database retrieval assistant. You MUST respond with JSON only.\n"
            "NEVER write educational content. ONLY retrieve links from database.\n\n"
            "Examples:\n"
            'User: "I need class 10 AI notes" → {"action": "get_notes", "arguments": {"class": "Class 10", "subject": "AI", "type": "Notes"}, "reply": ""}\n'
            'User: "class 12 CS books" → {"action": "get_notes", "arguments": {"class": "Class 12", "subject": "CS", "type": "Books"}, "reply": ""}\n'
            'User: "hello" → {"action": "reply", "arguments": {}, "reply": "Hi! What study materials do you need?"}\n\n'
            "STRICT RULES:\n"
            "1. For ANY study material request → use get_notes action\n"
            "2. For videos → use get_videos action\n"
            "3. class: 'Class 10', 'Class 11', or 'Class 12'\n"
            "4. subject: 'AI', 'IT', 'CS', or 'IP'\n"
            "5. type: 'Notes', 'Books', 'Syllabus', or 'Sample Question Papers SQP'\n"
            "6. If missing info → ask in reply field\n"
            "7. NEVER generate educational content\n"
            f"{recent_context}"
        )

        # Add to conversation history
        if not history:
            append_to_history(user_id, "system", system_prompt)
        append_to_history(user_id, "user", query)

        # Call OpenAI Responses API
        messages = build_responses_messages(user_conversations[user_id])
        resp = await asyncio.to_thread(
            get_client().responses.create,
            model="gpt-4o",
            input=messages,
            max_output_tokens=300,
        )

        # Parse response
        assistant_text = getattr(resp, "output_text", "{}")
        try:
            # Try to extract JSON if there's extra text
            if '{' in assistant_text and '}' in assistant_text:
                start = assistant_text.find('{')
                end = assistant_text.rfind('}') + 1
                json_text = assistant_text[start:end]
                decision = json.loads(json_text)
            else:
                decision = json.loads(assistant_text)
        except Exception as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response text: '{assistant_text}'")
            print(f"Response length: {len(assistant_text)}")
            decision = {"action": "reply", "reply": "Please specify class, subject, and type for your notes."}

        action = decision.get("action", "reply")
        arguments = decision.get("arguments", {})
        reply_text = decision.get("reply", "")

        # Execute action
        if action == "get_notes":
            if all(k in arguments for k in ["class", "subject", "type"]):
                print(f"Calling get_notes with: {arguments}")  # Debug
                result = await get_notes(arguments)
                append_to_history(user_id, "assistant", result)
                output["final_output"] = result
            else:
                missing = [k for k in ["class", "subject", "type"] if k not in arguments]
                msg = f"Please specify: {', '.join(missing)}. Available: Classes (10/11/12), Subjects (AI/IT/CS/IP), Types (Notes/Books/Syllabus/Sample Question Papers SQP)"
                append_to_history(user_id, "assistant", msg)
                output["final_output"] = msg
        elif action == "get_videos":
            if arguments.get("topic"):
                result = await get_videos(arguments)
                append_to_history(user_id, "assistant", result)
                output["final_output"] = result
            else:
                msg = "Please specify a topic for videos."
                append_to_history(user_id, "assistant", msg)
                output["final_output"] = msg
        else:
            reply = reply_text or "How can I help you with notes or videos?"
            append_to_history(user_id, "assistant", reply)
            output["final_output"] = reply

        return output

    except Exception as e:
        logging.getLogger(__name__).error(f"Intent classification error: {e}")
        fallback = "Sorry, I had trouble. Please try again."
        append_to_history(user_id, "assistant", fallback)
        output["final_output"] = fallback
        return output
