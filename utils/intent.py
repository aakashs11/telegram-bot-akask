import json
import asyncio
from typing import Dict, Any
import logging

from utils.screening import screen_message
from utils.common import append_to_history
from utils.openai_client import client, build_responses_messages
from functions.notes import get_notes
from functions.videos import get_videos
from utils.common import user_conversations


async def classify_intent(query: str, user_id: int, sh: Any = None) -> Dict[str, Any]:
    """
    Classify intent and execute actions using OpenAI Responses API with a JSON control protocol.

    Returns a dict with keys: output_screener, output_intent, output_entitites, final_output
    """
    output: Dict[str, Any] = {
        "output_screener": "",
        "output_intent": "",
        "output_entitites": "",
        "final_output": "",
    }

    try:
        # Quick slot-fill check: if last system message holds PENDING_SLOTS, try to auto-fill from current user query
        pending = None
        history = user_conversations.get(user_id, [])
        last_pending_msg = next(
            (
                m
                for m in reversed(history)
                if m.get("role") == "system"
                and isinstance(m.get("content", ""), str)
                and m["content"].startswith("PENDING_SLOTS::")
            ),
            None,
        )
        if last_pending_msg is not None:
            try:
                pending = json.loads(last_pending_msg["content"].split("::", 1)[1])
            except Exception:
                pending = None
        if pending:
            if pending.get("action") == "get_notes":
                args = pending.get("filled", {})
                # naive fills from current query text
                text = query.lower()
                if "class 10" in text and "class" not in args:
                    args["class"] = "Class 10"
                if "class 11" in text and "class" not in args:
                    args["class"] = "Class 11"
                if "class 12" in text and "class" not in args:
                    args["class"] = "Class 12"
                for subj in ["ai","it","cs","ip"]:
                    if subj in text and "subject" not in args:
                        args["subject"] = subj.upper()
                if "notes" in text and "type" not in args:
                    args["type"] = "Notes"
                missing = [f for f in ["type","class","subject"] if f not in args]
                if not missing:
                    result = await get_notes(args)
                    append_to_history(user_id, "assistant", result)
                    output["final_output"] = result
                    return output
            elif pending.get("action") == "get_videos":
                args = pending.get("filled", {})
                if "topic" not in args:
                    args["topic"] = query
                if args.get("topic"):
                    result = await get_videos(args)
                    append_to_history(user_id, "assistant", result)
                    output["final_output"] = result
                    return output

        # Heuristic fast-path for repository notes/videos to ensure links
        text_lower = query.strip().lower()
        if any(k in text_lower for k in ["notes", "sqp", "syllabus", "books"]):
            inferred: Dict[str, Any] = {}
            if "class 10" in text_lower:
                inferred["class"] = "Class 10"
            elif "class 11" in text_lower:
                inferred["class"] = "Class 11"
            elif "class 12" in text_lower:
                inferred["class"] = "Class 12"
            for subj in ["ai", "it", "cs", "ip"]:
                if f" {subj} " in f" {text_lower} ":
                    inferred["subject"] = subj.upper()
                    break
            if "sqp" in text_lower or "sample question" in text_lower:
                inferred["type"] = "Sample Question Papers SQP"
            elif "syllabus" in text_lower:
                inferred["type"] = "Syllabus"
            elif "books" in text_lower:
                inferred["type"] = "Books"
            elif "notes" in text_lower:
                inferred["type"] = "Notes"
            missing_fast = [f for f in ["type", "class", "subject"] if f not in inferred]
            if missing_fast:
                context_state = {"action": "get_notes", "needed": missing_fast, "filled": inferred}
                user_conversations[user_id].append({"role": "system", "content": f"PENDING_SLOTS::{json.dumps(context_state)}"})
                ask = f"Please specify: {', '.join(missing_fast)}."
                append_to_history(user_id, "assistant", ask)
                return {**output, "final_output": ask}
            else:
                result = await get_notes(inferred)
                append_to_history(user_id, "assistant", result)
                return {**output, "final_output": result}

        if any(k in text_lower for k in ["video", "videos"]):
            res = await get_videos({"topic": query})
            append_to_history(user_id, "assistant", res)
            return {**output, "final_output": res}

        screening = await screen_message(query)
        is_valid = bool(screening.get("is_valid", False))
        output["output_screener"] = is_valid
        if not is_valid:
            output["final_output"] = "Please use respectful language. [Warning]"
            return output

        system_prompt = (
            "You are ASK.ai, a concise assistant for students.\n"
            "Respond in under 30 words. Use a strict JSON control format ONLY.\n"
            "JSON schema: {\n"
            '  "action": "get_notes" | "get_videos" | "reply",\n'
            '  "arguments": {"class"?: string, "subject"?: string, "type"?: string, "topic"?: string},\n'
            '  "reply": string\n'
            "}\n"
            "- If the user wants links to notes/books/syllabus/SQP: set action=get_notes and fill arguments; DO NOT assume class/subject; ask for missing.\n"
            "- If the user wants videos by topic: set action=get_videos with {topic}.\n"
            "- Otherwise set action=reply with a short helpful message.\n"
        )

        # Ensure system prompt is first in a new conversation, then the user message
        history = user_conversations.get(user_id, [])
        if not history:
            append_to_history(user_id, "system", system_prompt)
        append_to_history(user_id, "user", query)

        # Build messages for Responses API (must use input_text per latest SDK)
        full_history_messages = build_responses_messages(user_conversations[user_id])

        try:
            resp = await asyncio.to_thread(
                client.responses.create,
                model="gpt-4o-mini",
                input=full_history_messages,
                max_output_tokens=300,
            )
        except Exception as history_err:
            logging.getLogger(__name__).warning(
                f"Responses API failed with full history: {history_err}. Retrying with system+user only."
            )
            minimal_ctx = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ]
            minimal_messages = build_responses_messages(minimal_ctx)
            resp = await asyncio.to_thread(
                client.responses.create,
                model="gpt-4o-mini",
                input=minimal_messages,
                max_output_tokens=300,
            )

        assistant_json_text = getattr(resp, "output_text", None) or "{}"
        # Heuristic: try to parse JSON; if it fails, fall back to reply mode
        try:
            decision = json.loads(assistant_json_text)
        except Exception as parse_err:
            logging.getLogger(__name__).warning(
                f"Assistant output not JSON. Using reply fallback. output_text={assistant_json_text[:200]}... error={parse_err}"
            )
            decision = {"action": "reply", "reply": assistant_json_text}

        action = decision.get("action", "reply")
        arguments = decision.get("arguments", {}) or {}
        suggested_reply = decision.get("reply", "")

        # Execute actions
        if action == "get_notes":
            missing = [f for f in ["type", "class", "subject"] if f not in arguments]
            if missing:
                # Persist pending slots for next user reply
                context_state = {"action": "get_notes", "needed": missing, "filled": arguments}
                user_conversations[user_id].append({"role": "system", "content": f"PENDING_SLOTS::{json.dumps(context_state)}"})
                msg = f"Please specify: {', '.join(missing)}."
                append_to_history(user_id, "assistant", msg)
                output["final_output"] = msg
            else:
                result = await get_notes(arguments)
                append_to_history(user_id, "assistant", result)
                output["final_output"] = result
        elif action == "get_videos":
            if not arguments.get("topic"):
                context_state = {"action": "get_videos", "needed": ["topic"], "filled": arguments}
                user_conversations[user_id].append({"role": "system", "content": f"PENDING_SLOTS::{json.dumps(context_state)}"})
                msg = "Please specify the topic for videos."
                append_to_history(user_id, "assistant", msg)
                output["final_output"] = msg
            else:
                result = await get_videos(arguments)
                append_to_history(user_id, "assistant", result)
                output["final_output"] = result
        else:
            reply = suggested_reply or "How can I help with notes or videos?"
            append_to_history(user_id, "assistant", reply)
            output["final_output"] = reply

        return output

    except Exception as e:
        fallback = "Sorry, I had trouble. Please try again."
        append_to_history(user_id, "assistant", fallback)
        output["final_output"] = fallback
        return output
