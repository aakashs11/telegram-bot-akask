from flask import Flask, request
import json
from telegram import Bot, Update  # Import Bot here
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import asyncio
import requests
from openai import OpenAI
from telegram.helpers import escape_markdown

# Initialize OpenAI client
client = OpenAI()
# Initialize Flask app
app = Flask(__name__)

# Conversation history
conversation_history = []

import re
def escape_markdown(text: str, version: str = "MarkdownV2") -> str:
    """
    Escapes special characters for Markdown formatting but preserves hyperlink formatting.

    Args:
        text (str): The input text to escape.
        version (str): The Markdown version. Defaults to MarkdownV2.

    Returns:
        str: Escaped text safe for Telegram messages.
    """
    if version == "MarkdownV2":
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
    else:
        escape_chars = r"\_*[]()"
    
    # Regex to match MarkdownV2 links ([text](url))
    link_pattern = re.compile(r"(\[.*?\]\(.*?\))")
    
    # Escape all text except for links
    parts = link_pattern.split(text)
    escaped_parts = [
        part if link_pattern.match(part) else "".join(f"\\{char}" if char in escape_chars else char for char in part)
        for part in parts
    ]
    
    return "".join(escaped_parts)



# Append to conversation history
def append_to_history(role, content):
    conversation_history.append({"role": role, "content": content})

def format_notes(data):
    """
    Formats the notes dictionary into a MarkdownV2-compatible string.

    Args:
        data (dict): Dictionary where keys are file names and values are URLs.

    Returns:
        str: Formatted string with file names as clickable links.
    """
    if not isinstance(data, dict):
        return "Notes data is not in the expected format."

    # Construct formatted response
    formatted_notes = []
    for file_name, url in data.items():
        # Escape the file name for MarkdownV2 compatibility
        escaped_file_name = escape_markdown(file_name)
        formatted_notes.append(f"[{escaped_file_name}]({url})")

    # Join all formatted links with newlines
    return "\n".join(formatted_notes)

def get_notes(query):
    print("Entered Get Notes, Query is:", query, type(query))
    try:
        if isinstance(query, str):
            query = json.loads(query)

        with open(".\config\index.json") as f:
            index = json.load(f)
            # print(index)

        # Extract required information
        _class = None
        _subject = None
        for entity in query.get("entities", []):
            if entity["type"] == "class":
                _class = entity["value"]
            elif entity["type"] == "subject":
                _subject = entity["value"]

        # Check if all required data is present
        if not _class:
            return "Could you please specify the class?"
        if not _subject:
            return "Could you please specify the subject?"

        # Retrieve notes
        data = index.get(_class, {}).get(_subject, "Notes not available")
        if data == "Notes not available":
            return data

        # Format the notes for output
        return format_notes(data)
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        return "Invalid JSON format."
    except FileNotFoundError:
        return "Index file not found."
    except Exception as e:
        print("Unexpected error:", e)
        return "An error occurred while processing the request."


# Tool definition
# Tool definition
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "Get the link to required notes. Call this whenever the user asks for notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "object",
                        "description": "The intent and associated entities for the query",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "description": "The user's intent, such as 'get_notes', 'get_syllabus','unknown_intent"
                            },
                            "entities": {
                                "type": "array",
                                "description": "A list of entities related to the query",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "description": "The type of the entity, such as 'subject', 'class', etc."
                                        },
                                        "value": {
                                            "type": "string",
                                            "description": "The value of the entity, such as 'AI', 'Class 10', etc. Valid values are ['AI','IT','IP','CS','CA'] and ['Class 10', 'Class 11'], 'Class 12'"
                                        }
                                    },
                                    "required": ["type", "value"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["intent", "entities"],
                        "additionalProperties": False
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
]
# Classify intent function
def classify_intent(query):
    append_to_history("user", query)

    
    prompt_classify_intent = """
    Given a user's query, identify the user's intent (e.g., get_notes, get_syllabus, unknown_intent), and extract entities such as subject (AI, IT, IP, CS) and class (Class 10, Class 11, Class 12). Normalize entities to standard values. If information is missing, dynamically ask for the missing details in a user-friendly way. Format the output in the following JSON:
    {
      "intent": "<intent>",
      "entities": [
        {
          "type": "<entity_type>",
          "value": "<entity_value>"
        }
      ]
    }
    STRICTLY Use the get_notes tool if the intent is get_notes.
    """
    if len(conversation_history) == 0:
        append_to_history("system", f" Given a user's query, identify the user's intent (e.g., get_notes, get_syllabus, unknown_intent), and extract entities such as subject (AI, IT, IP, CS) and class (Class 10, Class 11, Class 12). Normalize entities to standard values. If information is missing, dynamically ask for the missing details in a user-friendly way. Handle out of context queries gracefully. Give a warning if the user asks for anything other than educational context.")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        tools=tools,
        max_tokens=50
    )

    assistant_message = response.choices[0].message

    if assistant_message.tool_calls:
        tool_call = assistant_message.tool_calls[0]
        if tool_call.function.name == "get_notes":
            arguments = json.loads(tool_call.function.arguments)
            if "query" in arguments and arguments["query"].get("entities"):
                result = get_notes(arguments["query"])
                append_to_history("assistant", result)
                return result
            else:
                # Dynamically ask for missing information
                missing_info = []
                for required in ["class", "subject"]:
                    if not any(entity["type"] == required for entity in arguments["query"].get("entities", [])):
                        missing_info.append(required)
                missing_prompt = f"Could you please specify: {', '.join(missing_info)}?"
                append_to_history("assistant", missing_prompt)
                return missing_prompt

    # Handle responses without tool calls
    append_to_history("assistant", assistant_message.content)
    return escape_markdown(assistant_message.content
)
# Telegram bot token
TOKEN = '7559131288:AAFoveLB2DajT9KXXhrBcznEe9xLKhwqkh4'
# Initialize the Application
application = Application.builder().token(TOKEN).build()
#  Handlers
async def start(update: Update, context):
    user = update.effective_user
    await update.message.reply_text(f"Hi {user.first_name}! I'm a bot powered by OpenAI. Ask me anything!")

async def handle_message(update: Update, context):
    user_message = update.message.text
    # Implement your classify_intent function here
    response = classify_intent(user_message)
    escaped_response = escape_markdown(response, version=2)
    await update.message.reply_text(response, parse_mode="MarkdownV2")

# Add handlers to application
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)

        async def process_update():
            await application.initialize()  # Ensure the Application is initialized
            await application.process_update(update)  # Process the incoming update
            await application.shutdown()  # Graceful shutdown of the Application

        asyncio.run(process_update())  # Run the async function

        return 'OK', 200  # Respond with 200 OK to Telegram
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return 'Internal Server Error', 500


NGROK_URL = 'https://486f-49-207-216-250.ngrok-free.app/'
def set_webhook():
    webhook_url = f'{NGROK_URL}/webhook'
    response = requests.get(f'https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}')
    if response.status_code == 200:
        print("Webhook set successfully.")
    else:
        print(f"Failed to set webhook: {response.text}")

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000)