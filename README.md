# 🤖 ASK.ai - AI-Powered Telegram Study Assistant

> An intelligent Telegram bot that helps Indian students access educational resources using conversational AI, powered by OpenAI's GPT-4o-mini

[![Deploy](https://img.shields.io/badge/Deploy-Cloud%20Run-blue)](https://cloud.google.com/run)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## ✨ Features

🎯 **Smart Conversational Interface**
- Natural language understanding - no command memorization needed
- Context-aware responses with conversation history
- Automatic class/subject profile management with yearly progression

📚 **Resource Access**
- **Notes & Study Materials** - Organized by class, subject, and topic from Google Drive
- **Video Tutorials** - YouTube search integration for educational content  
- **Sample Papers & Books** - Quick access to exam resources

🛡️ **Safety & Moderation**
- AI-powered spam detection using GPT-4o-mini
- OpenAI Moderation API for content safety
- Automatic filtering of inappropriate messages

🔧 **Advanced Features**
- **Agentic AI** - Function calling with 4 specialized tools
- **Persistent Profiles** - Google Sheets backend for user data
- **Auto-sync** - Drive content sync every 5 minutes
- **Production Ready** - Deployed on Google Cloud Run with Secret Manager

---

## 🚀 Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for detailed setup instructions.

### Local Development (30 seconds)

```bash
# 1. Clone & install
git clone https://github.com/aakashs11/telegram-bot-akask.git
cd telegram-bot-akask
pipenv install

# 2. Configure .env
cp .env.example .env
# Edit .env with your tokens

# 3. Run with auto-reload
./start_devtest.sh
```

### Production Deployment (One Command!)

```bash
./deploy.sh
```

Deploys to Cloud Run, updates secrets, and configures webhook automatically.

---

## 📋 Architecture

### High-Level Overview

```
User Message → Telegram API → Cloud Run (FastAPI) → Agent Service
                                                          ↓
                        ← Response ← Tool Execution ← OpenAI GPT-4o-mini
```

### Project Structure

```
telegram-bot-akask/
├── main.py                      # FastAPI webhook handler
├── telegram_bot/
│   ├── application.py           # Bot initialization & dependency injection
│   ├── handlers.py              # Message routing & spam detection
│   ├── services/
│   │   ├── agent_service.py     # OpenAI function calling orchestration
│   │   ├── user_service.py      # Profile management (Google Sheets)
│   │   ├── note_service.py      # Notes retrieval with caching
│   │   ├── drive_service.py     # Google Drive scanning
│   │   ├── sync_service.py      # Background Drive → Sheets sync
│   │   └── moderation_service.py # Spam + content moderation
│   ├── tools/                   # Agent tools (SOLID design)
│   │   ├── notes_tool.py        # Search notes/books
│   │   ├── videos_tool.py       # YouTube search
│   │   ├── profile_tool.py      # Update user profile
│   │   └── list_resources_tool.py # Show available resources
│   ├── prompts/                 # Modular prompt templates
│   │   ├── agent_system.md      # Main agent system prompt
│   │   ├── profile_section.md   # User profile context
│   │   └── spam_detection.md    # Spam detection rules
│   └── infrastructure/
│       └── drive_note_repository.py # Drive + Sheets integration
├── config/
│   ├── settings.py              # Environment config + Secret Manager
│   └── model_config.py          # OpenAI model configurations
├── utils/                       # Helpers (formatting, logging, etc.)
├── scripts/                     # Admin tools (sync, inspect)
└── deploy.sh                    # One-command production deployment
```

## 📂 Content Management

The bot serves content (notes, books) from a Google Drive folder. To make files available to the bot, you must sync the Drive structure to the bot's index.

### Syncing Content
Run the sync script to scan your Drive folder and update the index:

```bash
# Local
python scripts/sync_drive.py

# Production (via Cloud Run job or manual script execution)
# Currently, you can run this locally with PROD credentials or implement a Cloud Scheduler job.
```

The script:
1. Scans the `DRIVE_FOLDER_ID` recursively
2. Categorizes files by Class/Subject/Unit
3. Updates the `index.json` (or Google Sheet backend) used by the bot

---

## 📜 Scripts Reference

| Script | Description | Usage |
|--------|-------------|-------|
| `deploy.sh` | **Production Deployment**. Builds & deploys to Cloud Run. | `./deploy.sh` |
| `start_devtest.sh` | **Local Development**. Sets up ngrok & runs bot. | `./start_devtest.sh` |
| `scripts/sync_drive.py` | **Content Sync**. Scans Drive & updates index. | `python scripts/sync_drive.py` |
| `scripts/inspect_drive.py` | **Debug**. Prints Drive folder structure. | `python scripts/inspect_drive.py` |
| `scripts/test_moderation.py` | **Safety Test**. Checks spam detection logic. | `python scripts/test_moderation.py "msg"` |

---

### Key Design Principles

1. **SOLID Architecture** - Tools implement `BaseTool` interface
2. **Dependency Injection** - Services passed via `bot_data`
3. **Clean Separation** - Domain, Infrastructure, Application layers
4. **Production-First** - Secret Manager, error handling, observability

---

## 🔧 Configuration

### Required Secrets (GCP Secret Manager)

| Secret Name | Description | Example |
|------------|-------------|---------|
| `telegram-bot-token` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `openai-api-key` | OpenAI API key | `sk-proj-...` |
| `youtube-api-key` | YouTube Data API v3 key | `AIza...` |
| `google-sheet-id` | Google Sheets ID for user profiles | `1abc...xyz` |
| `drive-folder-id` | Root Drive folder ID to scan | `1def...` |
| `cloud-run-url` | Auto-set by deploy script | `https://...` |

### Environment Variables

For local development (``.env`):

```bash
TELEGRAM_BOT_TOKEN=your_dev_bot_token
OPENAI_API_KEY=sk-proj-...
YOUTUBE_API_KEY=AIza...
SHEET_ID=1abc...
DRIVE_FOLDER_ID=1def...
NGROK_URL=https://xxxx.ngrok.io  # For local webhook
```

---

## 📊 Usage Examples

### Student Interaction

```
User: I need Class 10 AI notes

Bot: Here are the Class 10 AI resources:
     📄 Unit 1 Introduction to AI
     🔗 [Google Drive Link]
     📄 Unit 2 AI Project Cycle
     🔗 [Google Drive Link]
     ...
```

### Profile Management

```
User: I'm in Class 12 Computer Science

Bot: ✅ Profile updated!
     Class: 12
     Subject: Computer Science
     
     I'll remember this for next time!
```

### Video Search

```
User: Show me Python tutorials

Bot: 🎥 Found 5 videos:
     1. 📺 Python Full Course [Link]
     2. 📺 Data Structures in Python [Link]
     ...
```

---

## 🛠️ Development Workflow

See [DEVELOPMENT_WORKFLOW.md](./.gemini/antigravity/brain/.../DEVELOPMENT_WORKFLOW.md) for complete guide.

### Quick Reference

```bash
# Create feature branch
git checkout -b feat/feature-name

# Test locally with DEV bot
./start_devtest.sh

# Push & create PR
git push -u origin feat/feature-name

# After merge, deploy
git checkout main && git pull
./deploy.sh
```

---

## 🚢 Deployment

### Prerequisites

1. **GCP Project** with these APIs enabled:
   - Cloud Run
   - Secret Manager
   - Cloud Build
   - Artifact Registry

2. **Service Account** (`telegram-bot-user@...`) with roles:
   - Secret Manager Secret Accessor
   - Cloud Run Invoker

3. **Secrets** configured in Secret Manager (see Configuration)

### Deploy

```bash
./deploy.sh
```

This script:
- Builds container from source
- Deploys to Cloud Run (asia-south1)
- Updates `cloud-run-url` secret
- Configures Telegram webhook
- Verifies deployment

**Deployment time**: ~5-8 minutes

---

## 📈 Monitoring & Operations

### View Logs

```bash
# Tail logs in real-time
gcloud run services logs tail telegram-bot --region asia-south1

# View last 50 lines
gcloud run services logs read telegram-bot --region asia-south1 --limit=50

# Filter errors
gcloud run services logs read telegram-bot --region asia-south1 | grep ERROR
```

### Check Service Status

```bash
# Service details
gcloud run services describe telegram-bot --region asia-south1

# Get service URL
gcloud run services describe telegram-bot --region asia-south1 --format='value(status.url)'
```

### Verify Webhook

```bash
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq
```

Expected output:
- `pending_update_count`: 0
- `url`: Points to Cloud Run service
- `last_error_date`: Not present

---

## 🧪 Testing

### Manual Testing

Test against **DEV bot** locally:
```bash
./start_devtest.sh
# Message your DEV bot
```

Test against **PROD bot** after deployment:
```bash
# Send test messages to production bot
# Monitor logs for errors
```

### Automated Scripts

```bash
# Sync Drive manually
python scripts/sync_drive.py

# Inspect Drive structure
python scripts/inspect_drive.py

# Test moderation
python scripts/test_moderation.py "test message"
```

---

## 🐛 Troubleshooting

### Bot Not Responding

```bash
# Check webhook status
curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"

# Check Cloud Run logs
gcloud run services logs read telegram-bot --region asia-south1 --limit=20

# Restart service
gcloud run services update telegram-bot --region asia-south1
```

### Missing Dependencies Error

```bash
# Regenerate requirements.txt
pipenv requirements > requirements.txt

# Redeploy
git add requirements.txt
git commit -m "fix: Update dependencies"
git push origin main
./deploy.sh
```

### Secret Manager Permission Issues

```bash
SA_EMAIL="telegram-bot-user@telegram-bot-akask.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding telegram-bot-akask \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 📚 Documentation

- [QUICKSTART.md](./QUICKSTART.md) - Detailed setup guide
- [DEVELOPMENT_WORKFLOW.md](./.gemini/.../DEVELOPMENT_WORKFLOW.md) - Development process
- [Architecture Diagram](#architecture) - System design overview

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feat/amazing-feature`)
3. Test with DEV bot (`./start_devtest.sh`)
4. Commit changes (`git commit -m 'feat: Add amazing feature'`)
5. Push to branch (`git push origin feat/amazing-feature`)
6. Open Pull Request

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👨‍💻 Author

**Aakash Kehar Singh**
- GitHub: [@aakashs11](https://github.com/aakashs11)
- Email: aakash.mufc@gmail.com

---

## 🙏 Acknowledgments

- OpenAI for GPT-4o-mini API
- Google Cloud Platform for Cloud Run
- Telegram Bot API
- Python Telegram Bot library

---

**Made with ❤️ for students**