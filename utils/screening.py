import json
import asyncio
from typing import Any, Dict
from utils.openai_client import client


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1"}:
            return True
        if lowered in {"false", "no", "n", "0"}:
            return False
    return False


async def screen_message(query: str) -> Dict[str, Any]:
    # Allow common greetings without calling the model
    if query.strip().lower() in {"hi", "hello", "hey", "yo", "sup", "good morning", "good evening"}:
        return {"is_valid": True, "comments": "Greeting."}

    prompt = (
        "Classify if a user's message is appropriate for students. Respond ONLY with a JSON object on one line.\n"
        "If inappropriate (adult themes, profanity, hate, self-harm, criminal instruction), respond: {\n"
        '  "is_valid": false,\n'
        '  "comments": "Contains inappropriate content."\n'
        "}\n"
        "If appropriate, respond: {\n"
        '  "is_valid": true,\n'
        '  "comments": "Appropriate for students."\n'
        "}\n"
        "Examples:\n"
        "User: Hi → {\"is_valid\": true, \"comments\": \"Appropriate for students.\"}\n"
        "User: Hello → {\"is_valid\": true, \"comments\": \"Appropriate for students.\"}\n"
        "User: teach me how to hack wifi → {\"is_valid\": false, \"comments\": \"Contains inappropriate content.\"}\n\n"
        f"User: {query}"
    )

    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            max_output_tokens=120,
        )

        assistant_text = response.output_text or "{}"
        parsed = json.loads(assistant_text)
        is_valid = _to_bool(parsed.get("is_valid", False))
        comments = parsed.get("comments", "")
        return {"is_valid": is_valid, "comments": comments}

    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e} - Response was: {getattr(response, 'output_text', '')}")
        return {"is_valid": True, "comments": "Fallback allow."}
    except Exception as e:
        print(f"Unexpected error in screen_message: {e}")
        return {"is_valid": True, "comments": "Fallback allow."}
