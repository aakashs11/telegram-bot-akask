import os
from typing import List, Dict, Any

from openai import OpenAI


# Instantiate the official OpenAI client. The SDK will read the API key from
# the OPENAI_API_KEY environment variable. You can also pass it explicitly.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def build_responses_messages(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert a simple chat history of {"role": str, "content": str}
    into Responses API message format where content is an array of parts.

    Example input:
      [{"role": "system", "content": "..."}, {"role": "user", "content": "hi"}]

    Output:
      [
        {"role": "system", "content": [{"type": "text", "text": "..."}]},
        {"role": "user", "content": [{"type": "text", "text": "hi"}]}
      ]
    """
    messages: List[Dict[str, Any]] = []
    for message in history:
        role = message.get("role", "user")
        content = message.get("content", "")
        # Responses API requires assistant turns to use output_text/refusal
        if role == "assistant":
            content_part = {"type": "output_text", "text": content}
        else:
            content_part = {"type": "input_text", "text": content}

        messages.append({
            "role": role,
            "content": [content_part],
        })
    return messages

