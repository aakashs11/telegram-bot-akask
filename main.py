from fastapi import FastAPI, Request
import json
import asyncio
from telegram import Update
from contextlib import asynccontextmanager
import os
import requests
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
from pathlib import Path
import logging
import uvicorn
import subprocess
from google.cloud import secretmanager
import gspread
client = secretmanager.SecretManagerServiceClient()
secret_name = "projects/<project-id>/secrets/service-account-key/versions/latest"
response = client.access_secret_version(name=secret_name)
service_account_info = json.loads(response.payload.data.decode("UTF-8"))
from google.oauth2.service_account import Credentials
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
client = gspread.authorize(credentials)


# Configure logging
logging.basicConfig(level=logging.DEBUG,  # Set the desired logging level
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NGROK_URL = os.getenv("NGROK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")
logger.debug(f"Telegram Token: {TOKEN}, NGROK_URL: {NGROK_URL}, OPENAI_API_KEY: {OPENAI_API_KEY}")

# Initialize OpenAI client
from openai import OpenAI
client = OpenAI()

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    if CLOUD_RUN_URL:
        webhook_url = f"{CLOUD_RUN_URL}/webhook"
        response = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            params={"url": webhook_url}
        )
        if response.status_code == 200:
            logger.info(f"Webhook set successfully: {webhook_url}")
        else:
            logger.error(f"Failed to set webhook: {response.text}")
    else:
        logger.warning("CLOUD_RUN_URL is not set. The webhook will need to be configured manually after deployment.")
    yield

# After deployment, set the webhook using:
# curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
#      -H "Content-Type: application/json" \
#      -d '{"url": "https://<your-cloud-run-url>/webhook"}'
app = FastAPI(lifespan=lifespan)

# Initialize Telegram bot application
application = Application.builder().token(TOKEN).build()

##########################LOGGING##############


from googleapiclient.discovery import build
from google.oauth2 import service_account
# Open the Google Sheet by name
sheet = client.open('Telegram-Bot-Akask-Logs').sheet1
def log_to_sheet(user_id, user_message, bot_response):
    try:
        row = [user_id, user_message, bot_response]
        sheet.append_row(row)
    except Exception as e:
        logger.error(f"Failed to log to Google Sheets: {e}")




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

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

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

        with open("/app/config/index.json") as f:
            index = json.load(f)
            print(index)
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
                                "description": "The user's intent, such as 'get_notes', 'get_syllabus', etc."
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
                                            "description": "The value of the entity, such as 'AI', 'Class 10', etc. "
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
    
    def screen_message(query):
        screening_prompt = f"""
        Analyze the given message and determine if it is appropriate for students.
        The message should not contain adult, pornographic, or extreme language. or profanities in english and hindi.
        Keep output in under 15 words.
        Messages containing scientific or educational terms are always valid. 
        Respond in the following JSON format:
        {{
        "is_valid": "True/False",
        "comments": "Provide a brief explanation of why the message is valid or invalid."
        }}
        "This is an educational query: {query}"
        """
        messages =[ {"role": "system", "content": screening_prompt}]
        response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_format={ "type": "json_object" },
        max_tokens=30,
        messages=messages
        
    )
        assistant_message = response.choices[0].message.content
        try:
            assistant_message = json.loads(assistant_message)
        except Exception as e:
            print(e)
        
        return assistant_message

    message_is_valid = screen_message(query)['is_valid']
    if message_is_valid in ['True', 'true']:
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
        system_prompt= """
            You are ASK.ai a helpful assistant that provides notes and other asssistance based on user queries. 
            Greet the user with a message.
            Always ask for missing details if required.
            STRICTLY Use the get_notes tool if the intent is get_notes.
            STRICTLY FOLLOW THESE RULES:
            Age-Appropriate Language: Use clear, concise language suitable for teenagers. Explain complex terms when necessary.
            Empathy: Recognize signs of confusion or frustration. Respond with patience and offer additional explanations or resources.
            Refer to Human Assistance: For complex or sensitive issues, recommend seeking help from teachers or parents.
            Transparency: Inform users they are interacting with an AI and clarify its capabilities and limitations.
            STRICTLY Keep responses under 30 words.

            """
        # Add initial system message for context
        if len(conversation_history) == 0:
            append_to_history("system", system_prompt)

        # Get response from the model
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
    else:
        return "Please ensure your language is ethical and suitable for students."
# Handlers for Telegram
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(f"""Hi {user.first_name}! 
Hello! I'm Akask.ai, your AI-powered study buddy, here to assist with your educational needs. Here's how I can help:

📚 Class Notes: Access notes for classes 10-12.
🤔 General Doubts: Get answers to your questions across various subjects.

Coming Soon:
🧠 Subject-Specific Assistance: Detailed help tailored to each subject.
🎥 YouTube Video Links: Curated educational videos to enhance your learning.

💬 Tip: Talk to me in normal, simple language—no need to be formal! I'm here to make learning easy and fun for you. 😊

Feel free to start the conversation!""")

async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    
    user_id = update.message.from_user.id
    response = classify_intent(user_message)
    response = escape_markdown(response)
    await update.message.reply_text(response, parse_mode="MarkdownV2")
     # Log the interaction
    log_to_sheet(user_id, user_message, response)

# Add handlers to application
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
# Webhook endpoint
@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        # Ensure the application is initialized before processing updates
        await application.initialize()
        
        # Process the incoming webhook update
        update = Update.de_json(await request.json(), application.bot)
        await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error handling webhook")  # Use exception logging
        return {"status": "error", "message": str(e)}

# Run the FastAPI app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)