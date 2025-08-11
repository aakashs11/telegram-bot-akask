# ASK.ai Telegram Bot

A simple Telegram bot that helps students access educational resources like notes, videos, and study materials. Built with FastAPI, python-telegram-bot, and OpenAI's Responses API.

## 🏗️ Architecture

```
telegram-bot/
├── main.py                 # FastAPI server & webhook handler
├── telegram_bot/
│   ├── application.py      # Bot application setup
│   └── handlers.py         # Message handlers
├── functions/
│   ├── notes.py           # Notes/books retrieval from index
│   └── videos.py          # YouTube video search
├── utils/
│   ├── intent.py          # Basic intent classification
│   ├── screening.py       # Message content moderation
│   ├── openai_client.py   # OpenAI API client
│   ├── common.py          # Conversation history management
│   ├── formatting.py      # Markdown formatting utilities
│   └── gspread_logging.py # Google Sheets logging (optional)
├── config/
│   └── settings.py        # Environment configuration
├── data/
│   └── index.json         # Educational resources index
└── requirements.txt       # Python dependencies
```

## 🚀 Quick Start (Windows)

### Prerequisites
- Python 3.10+
- A Telegram bot token (create via BotFather)
- OpenAI API key
- Optional: Google Cloud credentials for Sheets logging

### Setup

1. **Clone and setup environment**:
   ```cmd
   cd telegram-bot
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables** (create `.env` file):
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   OPENAI_API_KEY=your_openai_key
   SHEET_ID=your_sheet_id (optional)
   ```

3. **Run locally**:
   ```cmd
   uvicorn main:app --host 0.0.0.0 --port 8080
   ```

### Local Testing with ngrok

1. **Install ngrok** (download from ngrok.com and add to PATH)

2. **Start tunnel**:
   ```cmd
   ngrok http 8080
   ```

3. **Set webhook** (replace with your ngrok URL):
   ```cmd
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" ^
        -H "Content-Type: application/json" ^
        -d "{\"url\": \"https://your-ngrok-url.ngrok-free.app/webhook\"}"
   ```

## 📝 Features

- **Notes & Resources**: Access study materials by class, subject, and type
- **Video Search**: Find educational videos on YouTube
- **Content Moderation**: Basic message screening
- **Conversation History**: Maintains context for better responses
- **Google Sheets Logging**: Optional interaction tracking

## 🛠️ Development

The bot uses a simple modular structure:

1. **Message Flow**: Telegram → FastAPI → Handlers → Intent Classification → Functions
2. **Intent Classification**: Uses OpenAI Responses API to determine user intent
3. **Functions**: Execute specific actions (get_notes, get_videos, or reply)
4. **Utilities**: Support functions for formatting, history, and logging

## 🚀 Deployment

Deploy to Google Cloud Run using the provided Dockerfile and cloudbuild.yaml configurations.

## 📋 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `SHEET_ID` | No | Google Sheet ID for logging |
| `INDEX_PATH` | No | Custom path to index.json |
| `CLOUD_RUN_URL` | No | Set for production webhook |

## 🔧 Troubleshooting

### Common Issues

1. **Port 8080 in use**:
   ```cmd
   netstat -aon | findstr :8080
   taskkill /PID <PID> /F
   ```

2. **ngrok not found**:
   - Download ngrok.exe and add to PATH
   - Or use full path: `C:\path\to\ngrok.exe http 8080`

3. **Bot not responding**:
   - Check webhook is set correctly
   - Verify ngrok tunnel is active
   - Check uvicorn logs for errors