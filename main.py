import asyncio
import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import gspread
import openai
import pytz
import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Update
from telegram.ext import (Application, CallbackContext, CommandHandler,
                          MessageHandler, filters)

print(os.environ.keys())
import google.auth

credentials, project = google.auth.default()
print(f"Service Account Email: {credentials.service_account_email}")

gc = gspread.authorize(credentials)
sh = gc.open_by_key("1-1Y4O4RAa-XgtAcGB_tEzXE3dta8pYxCgzj5o9FRqM0")
print("Spreadsheet opened successfully.")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the desired logging level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NGROK_URL = os.getenv("NGROK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
# service_account_key = os.getenv("service-account-key")
# if not service_account_key:
#     raise ValueError("SERVICE_ACCOUNT_KEY is not set or empty.")

CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")
logger.debug(
    f"Telegram Token: {TOKEN}, NGROK_URL: {NGROK_URL}, OPENAI_API_KEY: {OPENAI_API_KEY}"
)

# Initialize OpenAI client
from openai import OpenAI

client = OpenAI()

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")


# Attempt to open the spreadsheet
# try:
#     service_account_info = json.loads(service_account_key)

#     # credentials = Credentials.from_service_account_info(service_account_info)

#     print("Spreadsheet opened successfully.")
# except gspread.exceptions.SpreadsheetNotFound:
#     print("Spreadsheet not found. Please check the name and sharing settings.")


def log_to_sheet(
    user_id, username, input_message, screen_output, intent, entities, final_output
):
    try:
        # Get current date and time in IST
        ist = pytz.timezone("Asia/Kolkata")
        current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        # Prepare the row for logging
        row = [
            current_time,  # Timestamp
            user_id,  # User ID
            username,  # Username
            input_message,  # User's input
            screen_output,  # Screening comments
            intent,  # Detected intent
            entities,  # Extracted entities as JSON string
            final_output,  # Final response sent
        ]

        # Append the row to the Google Sheet
        worksheet = sh.sheet1  # Assuming the first sheet is used
        worksheet.append_row(row)
    except Exception as e:
        logger.error(f"Failed to log query details to Google Sheets: {e}")


# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    if CLOUD_RUN_URL:
        webhook_url = f"{CLOUD_RUN_URL}/webhook"
        response = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            params={"url": webhook_url},
        )
        if response.status_code == 200:
            logger.info(f"Webhook set successfully: {webhook_url}")
        else:
            logger.error(f"Failed to set webhook: {response.text}")
    else:
        logger.warning(
            "CLOUD_RUN_URL is not set. The webhook will need to be configured manually after deployment."
        )
    yield


# After deployment, set the webhook using:
# curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
#      -H "Content-Type: application/json" \
#      -d '{"url": "https://<your-cloud-run-url>/webhook"}'
app = FastAPI(lifespan=lifespan)

# Initialize Telegram bot application
application = Application.builder().token(TOKEN).build()

# Conversation history
conversation_history = []
# Dictionary to store conversation history for each user
user_conversations = {}


import re


def format_videos(video_data):
    """
    Formats a list of video dictionaries into a MarkdownV2-compatible string.

    Args:
        video_data (list): List of dictionaries containing video details.

    Returns:
        str: Formatted string with video titles as clickable links.
    """
    if not isinstance(video_data, list):
        return "Video data is not in the expected format."

    formatted_videos = []
    for video in video_data:
        title = video.get("title", "No Title")
        url = video.get("url", "#")
        # description = video.get('description', 'No Description')

        # Escape Markdown characters
        escaped_title = escape_markdown(title)
        # escaped_description = escape_markdown(description)

        # Format as Markdown link
        formatted_videos.append(f"[{escaped_title}]({url})")

    return "\n\n".join(formatted_videos)


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
        part
        if link_pattern.match(part)
        else "".join(f"\\{char}" if char in escape_chars else char for char in part)
        for part in parts
    ]

    return "".join(escaped_parts)


@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}


def append_to_history(user_id, role, content):
    # Initialize history for the user if not already present
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    # Append the new message to the user's history
    user_conversations[user_id].append({"role": role, "content": content})

    # Trim the history if it exceeds the maximum size
    MAX_HISTORY_SIZE = 3  # Adjust as needed
    if len(user_conversations[user_id]) > MAX_HISTORY_SIZE:
        user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY_SIZE:]


def format_notes(data):
    """
    Formats the notes dictionary into a MarkdownV2-compatible string.
    Args:
        data (dict): Nested dictionary where keys are topics or file names and values are URLs or further dicts.
    Returns:
        str: Formatted string with file names as clickable links.
    """
    if not isinstance(data, dict):
        return "Notes data is not in the expected format."

    formatted_notes = []

    def recurse_format(d, parent_keys=[]):
        for key, value in d.items():
            if isinstance(value, dict):
                # It's a nested dict, recurse
                recurse_format(value, parent_keys + [key])
            else:
                # It's a file/link
                # Build the display name with parent keys (e.g., Topic > File Name)
                display_name = " > ".join(parent_keys + [key])
                escaped_name = escape_markdown(display_name)
                formatted_notes.append(f"[{escaped_name}]({value})")

    recurse_format(data)
    return "\n".join(formatted_notes)


def get_notes(query):
    print("Entered Get Notes, Query is:", query, type(query))

    if isinstance(query, str):
        query = json.loads(query)

    with open("/app/config/index-v2.json") as f:
        index = json.load(f)
        print(index)

        # Extract required information
    class_name = None
    subject = None
    topic = None

    class_name = query["class"]
    subject = query["subject"]
    query_type = query["type"]
    print(class_name, subject)

    try:
        # Retrieve notes
        data = index[class_name][subject][query_type]
    except:
        return "Not available, Please try with other inputs or contact the admin!"

    try:
        topic = query["topic"]
        topic_data = data[topic]
        return format_notes(
            topic_data
        )  # Or use format_notes(topic_data) if formatting is needed
    except:
        return format_notes(data)  # Or use format_notes(data) if formatting is needed



async def get_videos(query):
    print("Entered Get Videos for", query["topic"])
    max_results = 5

    """
    Search for videos within a specific YouTube channel.

    Parameters:
        query (str): The search term.
        max_results (int): Maximum number of search results to return.

    Returns:
        list: A list of dictionaries containing video details (title, URL, description).
    """
    try:
        youtube = await asyncio.to_thread(
            build, 
            YOUTUBE_API_SERVICE_NAME, 
            YOUTUBE_API_VERSION, 
            developerKey=YOUTUBE_API_KEY
        )
        request = youtube.search().list(
            q=query,
            part="snippet",
            channelId="UCsHJyKNfjVMr4EoXPw-8Jxw",
            type="video",
            maxResults=max_results,
        )
        response = await asyncio.to_thread(request.execute)
        print("response is", response)
        results = []
        for item in response.get("items", []):
            video = {
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                # "description": item["snippet"]["description"]
            }
            results.append(video)

        return format_videos(results)
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return []


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "Retrieve the link to required notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class": {
                        "type": "string",
                        "enum": ["Class 10", "Class 11", "Class 12"],
                    },
                    "subject": {"type": "string", "enum": ["AI", "IT", "CS", "IP"]},
                    "type": {
                        "type": "string",
                        "enum": [
                            "Notes",
                            "Books",
                            "Syllabus",
                            "Sample Question Papers SQP",
                        ],
                    },
                },
                # "required": ["class", "subject"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_videos",
            "description": "Retrieve the links to required videos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        # "enum": ["Class 10", "Class 11", "Class 12"],
                    }
                },
            },
            "required": ["query"],
        },
    },
]


def screen_message(query):
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
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={"type": "json_object"},
            max_tokens=50,
            messages=messages,
        )
        assistant_message = response.choices[0].message.content
        parsed_response = json.loads(assistant_message)
        print(parsed_response)

        # Validate keys in the response
        if "is_valid" in parsed_response and "comments" in parsed_response:
            return parsed_response
        else:
            raise ValueError("Invalid response structure: Missing required keys.")

    except json.JSONDecodeError as e:
        print(
            f"JSONDecodeError: {e} - Response was: {response.choices[0].message.content}"
        )
        return {"is_valid": "False", "comments": "Could not parse response."}

    except Exception as e:
        print(f"Unexpected error in screen_message: {e}")
        return {
            "is_valid": "False",
            "comments": "An error occurred during screening.",
        }


# Classify intent function
def classify_intent(query, user_id):
    output = {
        "output_screener": "",
        "output_intent": "",
        "output_entitites": "",
        "final_output": "",
    }

    if user_id not in user_conversations:
        user_conversations[user_id] = []
    user_history = user_conversations[user_id]

    message_is_valid = screen_message(query)["is_valid"]
    output["output_screener"] = message_is_valid
    if message_is_valid:
        append_to_history(user_id, "user", query)

        system_prompt = f"""
            CHECK CONVERSATION HISTORY BEFORE RESPONDING.
            You are ASK.ai a helpful assistant that provides notes and other asssistance based on user queries. 
            Greet the user with a message saying who you are. Solve doubts or help with notes adn other items.
            STRICTLY ask for missing details if required. STRICTLY DON'T ASSUME THE CLASS.
            STRICTLY Use get_notes tool if the intent is to get notes.
            STRICTLY Use get_videos tool if the intent is to get videos. 
            STRICTLY Keep responses under 30 words. Summarize where necessary as long messages will be truncated.

            """
        # Add initial system message for context
        if len(user_history) == 0:
            append_to_history(user_id, "system", system_prompt)

        # Get response from the model
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_history,
            tools=tools,
            max_tokens=200,
        )
        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            tool_call = assistant_message.tool_calls[0]
            print("Tool is present", tool_call)
            if tool_call.function.name == "get_notes":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    print("Arguments are:", arguments)
                    # Handle missing information
                    required_fields = ["type", "class", "subject"]
                    missing_info = [
                        field for field in required_fields if field not in arguments
                    ]
                    print("missing info", missing_info)
                    if missing_info:
                        prompt = f"Could you please specify the following: {', '.join(missing_info)}?"
                        append_to_history(user_id, "assistant", prompt)
                        output["final_output"] = prompt
                    else:
                        # Call the get_notes function
                        result = get_notes(arguments)
                        append_to_history(user_id, "assistant", result)
                        output["final_output"] = result
                except json.JSONDecodeError as e:
                    output[
                        "final_output"
                    ] = "Error decoding function arguments. Please try again."
            elif tool_call.function.name == "get_videos":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    print("Arguments are:", arguments)
                    # Handle missing information
                    required_fields = ["topic"]
                    missing_info = [
                        field for field in required_fields if field not in arguments
                    ]
                    print("missing info", missing_info)
                    if missing_info:
                        prompt = f"Could you please specify the {', '.join(missing_info)}"
                        append_to_history(user_id, "assistant", prompt)
                        output["final_output"] = prompt
                    else:
                        # Call the get_notes function
                        result = get_videos(arguments)
                        append_to_history(user_id, "assistant", result)
                        output["final_output"] = result
                except json.JSONDecodeError as e:
                    output[
                        "final_output"
                    ] = "Error decoding function arguments. Please try again."
            else:
                # append_to_history("assistant", "Unsupported function call.")
                output["final_output"] = "Unsupported function call."
        else:
            # Regular assistant message
            append_to_history(user_id, "assistant", assistant_message.content)
            output["final_output"] = assistant_message.content

    else:
        return "Please use respectful language. [Warning]"
    return output


# Handlers for Telegram
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(
        f"""Hi {user.first_name}! 
Hello! I'm Akask.ai, your AI-powered study buddy, here to assist with your educational needs. Here's how I can help:

📚 Class Notes: Access notes for classes 10-12.
🤔 General Doubts: Get answers to your questions across various subjects.

Coming Soon:
🧠 Subject-Specific Assistance: Detailed help tailored to each subject.
🎥 YouTube Video Links: Curated educational videos to enhance your learning.

💬 Tip: Talk to me in normal, simple language—no need to be formal! I'm here to make learning easy and fun for you. 😊

Feel free to start the conversation!"""
    )


async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    user_id = update.message.from_user.id
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username
    output = await asyncio.to_thread(classify_intent, user_message, user_id)
    response = output["final_output"]
    response = escape_markdown(response)
    await update.message.reply_text(response, parse_mode="MarkdownV2")

    log_to_sheet(
        user_id=user_id,
        username=username,
        input_message=user_message,
        screen_output=output["output_screener"],
        intent=output["output_intent"],
        entities=output["output_entitites"],
        final_output=output["final_output"],
    )


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
