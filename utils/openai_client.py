import os
from typing import List, Dict, Any

from openai import OpenAI

# Lazy initialization of the OpenAI client
_client = None

def get_client():
    """Get or create OpenAI client instance"""
    global _client
    if _client is None:
        from config.settings import OPENAI_API_KEY
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured in settings")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


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

