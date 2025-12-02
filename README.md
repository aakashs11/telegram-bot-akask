# 🤖 ASK AI - AI-Powered Telegram Study Assistant

> An intelligent Telegram bot that helps Indian students access educational resources using conversational AI, powered by OpenAI's GPT-4o

[![Deploy](https://img.shields.io/badge/Deploy-Cloud%20Run-blue)](https://cloud.google.com/run)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## ✨ Features

🎯 **Smart Conversational Interface**
- Natural language understanding - no command memorization needed
- Context-aware responses with conversation history
- Automatic class/subject profile management with yearly progression
- Quote-reply support in group chats for contextual responses

📚 **Resource Access**
- **Notes & Study Materials** - Organized by class, subject, and topic from Google Drive
- **Video Tutorials** - YouTube search integration for educational content  
- **Sample Papers & Books** - Quick access to exam resources

🛡️ **Advanced Moderation System** (NEW!)
- **Single LLM Moderation** - GPT-4o-mini for spam + abuse + safety in one call
- **Multi-language Abuse Detection** - Hindi (Roman + Devanagari), Hinglish, English
- **Warning & Ban System** - 2-strike policy with automatic bans
- **Auto-delete** - Flagged messages deleted instantly
- **Private Warnings** - Users notified via DM (not in group)
- **Persistent Tracking** - Warnings logged in Google Sheets

🔧 **Advanced Features**
- **Agentic AI** - Function calling with 4 specialized tools
- **Persistent Profiles** - Google Sheets backend for user data
- **Auto-sync** - Drive content sync every 5 minutes
- **Production Ready** - Deployed on Google Cloud Run with Secret Manager
- **Unified Architecture** - Same moderation for private and group chats

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** and **pipenv**
2. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
3. **OpenAI API Key** from [OpenAI Platform](https://platform.openai.com)
4. **Google Cloud Project** with:
   - Service Account JSON for Sheets/Drive access
   - YouTube Data API v3 enabled
5. **ngrok** for local development

### 1. Clone & Install (2 minutes)

```bash
git clone https://github.com/aakashs11/telegram-bot-akask.git
cd telegram-bot-akask
pipenv install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
OPENAI_API_KEY=sk-proj-...
YOUTUBE_API_KEY=AIza...
SHEET_ID=your_google_sheet_id
DRIVE_FOLDER_ID=your_drive_folder_id
```

Add `service_account.json` to root folder (from Google Cloud Console).

### 3. Run Development Server

```bash
./start_devtest.sh
```

This script:
- Starts uvicorn server on port 8080
- Starts ngrok tunnel
- Sets Telegram webhook automatically
- Shows live logs

**That's it!** Message your bot to test.

---

## 📖 How to Add/Update Content

### Adding Notes (Google Drive)

1. **Navigate to your Drive folder** (the one in `DRIVE_FOLDER_ID`)
2. **Create folder structure:**
   ```
   📁 Your Drive Folder
   ├── 📁 Class 10
   │   ├── 📁 AI
   │   │   ├── 📄 Unit 1 Introduction.pdf
   │   │   └── 📄 Unit 2 AI Cycle.pdf
   │   └── 📁 Science
   │       └── 📄 Physics Notes.pdf
   └── 📁 Class 12
       └── 📁 Computer Science
           └── 📄 Python Basics.pdf
   ```
3. **Wait 5 minutes** - Auto-sync picks up new files
4. **Or force sync:**
   ```bash
   python scripts/sync_drive.py
   ```

### Adding Moderation Rules

Edit `telegram_bot/prompts/content_moderation.md`:
```markdown
FLAG if ANY of these:
- Spam: promotions, "free project/course" scams
- Abuse: profanity, slurs (ANY language)
- Your custom rule here

ALLOW:
- Normal questions
- Your exceptions here
```

### Updating Warning Messages

Edit `telegram_bot/services/moderation/warning_service.py` (lines 190-220).

---

## 📋 Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Message                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     handlers.py                              │
│                   (thin routing layer)                       │
└─────────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────────┐
│   GroupOrchestrator     │    │    Private Chat Handler     │
│   ├─ ContentModerator   │    │    ├─ ContentModerator      │
│   ├─ WarningService     │    │    └─ AgentService          │
│   ├─ GroupHelper        │    │                             │
│   └─ AgentService       │    │                             │
└─────────────────────────┘    └─────────────────────────────┘
```

### Project Structure

```
telegram-bot-akask/
├── main.py                           # FastAPI webhook handler
├── telegram_bot/
│   ├── application.py                # Bot initialization & DI
│   ├── handlers.py                   # Message routing (thin layer)
│   ├── services/
│   │   ├── agent_service.py          # OpenAI function calling
│   │   ├── user_service.py           # Profile management (Sheets)
│   │   ├── note_service.py           # Notes retrieval
│   │   ├── drive_service.py          # Google Drive scanning
│   │   ├── sync_service.py           # Background sync
│   │   ├── message_service.py        # Unified message sending
│   │   ├── moderation/               # 🆕 Moderation module
│   │   │   ├── content_moderator.py  # Single LLM moderation
│   │   │   └── warning_service.py    # Warning + ban tracking
│   │   └── group/                    # 🆕 Group module
│   │       ├── group_orchestrator.py # Coordinates group logic
│   │       └── group_helper.py       # Context extraction
│   ├── tools/                        # Agent tools (SOLID)
│   │   ├── notes_tool.py
│   │   ├── videos_tool.py
│   │   ├── profile_tool.py
│   │   └── list_resources_tool.py
│   ├── prompts/                      # Prompt templates
│   │   ├── agent_system.md
│   │   ├── content_moderation.md     # 🆕 Unified moderation
│   │   └── spam_detection.md         # (legacy)
│   └── commands/
│       ├── welcome_command.py
│       └── notes_command.py
├── evals/                            # 🆕 Evaluation suite
│   ├── moderation_eval.py            # 75 test cases
│   └── results/
├── config/
│   ├── settings.py
│   └── model_config.py
├── scripts/                          # Admin tools
├── start_devtest.sh                  # Dev server script
└── deploy.sh                         # Production deployment
```

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| **SRP** | Each service has one responsibility |
| **DRY** | ContentModerator shared across all chats |
| **Thin Handlers** | Routing only, no business logic |
| **Dependency Injection** | Services passed via `bot_data` |
| **Prompt Files** | All prompts in `.md` files, not code |

---

## 🛡️ Moderation System

### How It Works

1. **Every message** in groups is checked (not just @mentions)
2. **Single LLM call** - GPT-4o-mini returns YES/NO
3. **Flagged messages** are deleted immediately
4. **Warning sent via DM** - no group spam
5. **2 strikes = ban** - automatic removal

### Test Cases

Run the evaluation suite:
```bash
pipenv run python -m evals.moderation_eval --verbose
```

| Category | Test Cases | Description |
|----------|-----------|-------------|
| Spam | 10 | t.me links, free courses |
| Hindi Severe | 20 | bc, mc, bsdk (Roman script) |
| Hindi Mild | 10 | pagal, bewakoof |
| Hindi Devanagari | 10 | चूतिया, मादरचोद |
| English Abuse | 10 | profanity, slurs |
| Safe (NOT flag) | 15 | Normal conversation |

### Warning Flow

```
1st Violation → ⚠️ WARNING 1/2 (DM) + Message Deleted
2nd Violation → 🛑 FINAL WARNING 2/2 (DM) + Message Deleted  
3rd Violation → 🚫 BANNED + Removed from Group
```

---

## 🔧 Common Tasks

### Deploy to Production

```bash
./deploy.sh
```

### Run Moderation Eval

```bash
pipenv run python -m evals.moderation_eval --save
```

### Force Drive Sync

```bash
pipenv run python scripts/sync_drive.py
```

### View Production Logs

```bash
gcloud run services logs tail telegram-bot --region asia-south1
```

### Check Webhook Status

```bash
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq
```

---

## 🗺️ Roadmap

### Completed ✅
- [x] Agentic AI with function calling
- [x] Google Drive integration
- [x] YouTube video search
- [x] User profile management
- [x] Spam detection with LLM
- [x] Multi-language abuse detection (Hindi/English)
- [x] Warning and ban system
- [x] Quote-reply context in groups
- [x] Unified moderation for all chats
- [x] Evaluation suite (75 test cases)

### Planned 🚧
- [ ] Appeal system for bans
- [ ] Admin dashboard (Telegram mini-app)
- [ ] Rate limiting per user
- [ ] Analytics and reporting
- [ ] Multi-group management
- [ ] Scheduled announcements
- [ ] PDF question answering (RAG)

### Future Ideas 💡
- [ ] Voice message support
- [ ] Image/diagram recognition
- [ ] Doubt resolution tracking
- [ ] Study streak gamification
- [ ] Integration with school LMS

---

## 🐛 Troubleshooting

### Bot Not Responding in Groups

1. Check if bot has admin rights (to delete messages)
2. Verify `can_read_all_group_messages` is enabled in BotFather
3. Check logs: `tail -f /tmp/telegram-bot-server.log`

### Moderation Not Working

```bash
# Test moderation directly
pipenv run python -c "
from telegram_bot.services.moderation import ContentModerator
import asyncio
m = ContentModerator()
print(asyncio.run(m.check('test message')))
"
```

### NoneType Error in Handlers

This happens with edited messages or channel posts. The guard is in place:
```python
if not update.message or not update.message.text:
    return
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👨‍💻 Author

**Aakash Kehar Singh**
- GitHub: [@aakashs11](https://github.com/aakashs11)
- Email: aakash.mufc@gmail.com

---

**Made with ❤️ for students**
