import json
import asyncio
from utils.openai_client import client

async def screen_message(query):
    """
    Screens the user's message to ensure it's appropriate for students.
    Returns a dict with keys 'is_valid' (bool) and 'comments' (str).
    """
    screening_prompt = f"""
    You are an AI assistant that determines if a user's message is appropriate for students.
    - If the message contains inappropriate content (adult themes, profanity, hate speech, etc.), respond with:
    {{
    "is_valid": false,
    "comments": "Contains inappropriate content."
    }}
    - If the message is appropriate, respond with:
    {{
    "is_valid": true,
    "comments": "Appropriate for students."
    }}
    Respond only with the JSON object, and no additional text.
    "This is an educational query: {query}"
    """

    messages = [{"role": "system", "content": screening_prompt}]
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo",
            response_format={"type": "json_object"},
            max_tokens=50,
            messages=messages
        )

        assistant_message = response.choices[0].message.content
        parsed_response = json.loads(assistant_message)

        if "is_valid" in parsed_response and "comments" in parsed_response:
            return parsed_response
        else:
            raise ValueError("Invalid response structure: Missing required keys.")

    except json.JSONDecodeError:
        return {"is_valid": False, "comments": "Could not parse response."}
    except Exception as e:
        return {"is_valid": False, "comments": f"An error occurred during screening: {e}"}
