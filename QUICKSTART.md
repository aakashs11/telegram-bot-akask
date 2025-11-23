# 🚀 QUICKSTART - ASK.ai Telegram Bot

Get your bot running locally or in production in under 10 minutes!

---

## 📋 Prerequisites

- **Python 3.10+** installed
- **Telegram Account** to create a bot
- **OpenAI API Key** ([get one here](https://platform.openai.com/api-keys))
- **Google Cloud Account** (for production deployment)

---

## ⚡ Local Development Setup

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow prompts
3. Choose a name: `My Study Bot`
4. Choose a username: `my_study_bot` (must end in `bot`)
5. **Copy the bot token** (looks like `123456:ABC-DEF...`)

### Step 2: Get API Keys

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-...`)

#### YouTube API Key
1. Go to https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" → "API Key"
3. Copy the key

#### Google Sheets Setup
1. Create a new Google Sheet
2. Copy the ID from URL: `docs.google.com/spreadsheets/d/`**`YOUR_SHEET_ID`**`/edit`
3. Share the sheet with your service account email

### Step 3: Clone & Install

```bash
# Clone repository
git clone https://github.com/aakashs11/telegram-bot-akask.git
cd telegram-bot-akask

# Install Pipenv (if not installed)
pip install pipenv

# Install dependencies
pipenv install
```

### Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=sk-proj-your_key_here
YOUTUBE_API_KEY=your_youtube_key_here

# Optional (for user profiles)
SHEET_ID=your_google_sheet_id

# Optional (for notes sync)
DRIVE_FOLDER_ID=your_drive_folder_id

# Auto-set by start_devtest.sh
NGROK_URL=  # Leave empty
```

### Step 5: Place Service Account Key

1. Download your Google Cloud service account JSON key
2. Save it as `service_account.json` in project root
3. This file is gitignored for security

### Step 6: Run the Bot!

#### Option A: Automated (Recommended)

```bash
./start_devtest.sh
```

This script automatically:
- Activates pipenv environment
- Stops existing ngrok tunnels
- Starts new ngrok tunnel
- Sets bot webhook
- Runs bot with hot reload

**Test it**: Send a message to your bot on Telegram!

#### Option B: Manual

```bash
# Activate environment
pipenv shell

# Start ngrok (in separate terminal)
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)

# Set webhook
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -d "url=https://abc123.ngrok.io/webhook"

# Run bot
python main.py
```

### Step 7: Sync Content (Important!)

The bot needs to know what files are in your Google Drive. Run the sync script:

```bash
python scripts/sync_drive.py
```

This scans your `DRIVE_FOLDER_ID` and updates the index. **Run this whenever you add new files to Drive.**

---

## ☁️ Production Deployment (Google Cloud Run)

### Prerequisites

1. **Google Cloud Project** created
2. **gcloud CLI** installed ([install guide](https://cloud.google.com/sdk/docs/install))
3. **Authenticated**: `gcloud auth login`

### Step 1: Enable Required APIs

```bash
gcloud services enable run.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

### Step 2: Create Service Account

```bash
PROJECT_ID="your-project-id"

# Create service account
gcloud iam service-accounts create telegram-bot-user \
  --display-name="Telegram Bot Runtime Account" \
  --project=$PROJECT_ID

# Grant permissions
SA_EMAIL="telegram-bot-user@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 3: Create Secrets

```bash
# Telegram bot token
echo -n "YOUR_BOT_TOKEN" | gcloud secrets create telegram-bot-token \
  --data-file=- \
  --project=$PROJECT_ID

# OpenAI API key
echo -n "YOUR_OPENAI_KEY" | gcloud secrets create openai-api-key \
  --data-file=- \
  --project=$PROJECT_ID

# YouTube API key
echo -n "YOUR_YOUTUBE_KEY" | gcloud secrets create youtube-api-key \
  --data-file=- \
  --project=$PROJECT_ID

# Google Sheet ID
echo -n "YOUR_SHEET_ID" | gcloud secrets create google-sheet-id \
  --data-file=- \
  --project=$PROJECT_ID

# Drive Folder ID
echo -n "YOUR_DRIVE_FOLDER_ID" | gcloud secrets create drive-folder-id \
  --data-file=- \
  --project=$PROJECT_ID

# Service account key (for Google APIs)
gcloud secrets create service-account-key \
  --data-file=service_account.json \
  --project=$PROJECT_ID

# Cloud Run URL (will be auto-updated by deploy script)
echo -n "placeholder" | gcloud secrets create cloud-run-url \
  --data-file=- \
  --project=$PROJECT_ID
```

### Step 4: Deploy!

```bash
# Update project ID in deploy.sh if needed
# Then run:
./deploy.sh
```

**Deployment takes ~5-8 minutes**

The script will:
- Build Docker container from source
- Deploy to Cloud Run in `asia-south1`
- Update `cloud-run-url` secret
- Configure Telegram webhook
- Display verification info

### Step 5: Verify Deployment

```bash
# Check service is running
gcloud run services describe telegram-bot --region asia-south1

# View logs
gcloud run services logs tail telegram-bot --region asia-south1

# Verify webhook
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq
```

**Expected webhook status:**
- `url`: Points to your Cloud Run service
- `pending_update_count`: 0
- No `last_error_date`

### Step 6: Test Production Bot

Send a message to your **production** bot on Telegram:

```
You: I need Class 10 AI notes

Bot: 📚 Here are the Class 10 AI resources...
```

### Step 7: Post-Deployment Setup (Sync Content)

To make your Drive content available to the production bot, run the sync script locally (it updates the shared Google Sheet/Index):

```bash
python scripts/sync_drive.py
```

---

## 🎯 Common Commands Cheat Sheet

### Local Development

```bash
# Start dev environment (auto-configures everything)
./start_devtest.sh

# Manual start
pipenv shell
python main.py

# Sync Drive content
python scripts/sync_drive.py

# Check ngrok status
curl http://localhost:4040/api/tunnels

# View local logs
# (logs appear in terminal where main.py is running)
```

### Production

```bash
# Deploy
./deploy.sh

# View logs
gcloud run services logs tail telegram-bot --region asia-south1

# Restart service
gcloud run services update telegram-bot --region asia-south1

# Check webhook
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feat/my-feature

# After changes
git add .
git commit -m "feat: Description"
git push -u origin feat/my-feature

# After PR merge
git checkout main
git pull
./deploy.sh  # Deploy to production
```

---

## ❓ Troubleshooting

### "Bot not responding" (Local)

```bash
# Check ngrok is running
curl http://localhost:4040/api/tunnels

# Check webhook is set
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"

# Restart ngrok
pkill ngrok
ngrok http 8000
# Then re-set webhook with new URL
```

### "ModuleNotFoundError" (Production)

```bash
# Regenerate requirements
pipenv requirements > requirements.txt

# Redeploy
git add requirements.txt
git commit -m "fix: Update requirements"
git push origin main
./deploy.sh
```

### "Permission denied" on Secret

```bash
# Grant Secret Manager access
SA_EMAIL="telegram-bot-user@PROJECT_ID.iam.gserviceaccount.com"

gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 📚 Next Steps

- [ ] Customize prompts in `telegram_bot/prompts/`
- [ ] Add more tools in `telegram_bot/tools/`
- [ ] Set up Google Drive sync for notes
- [ ] Configure user profiles with Google Sheets
- [ ] Review [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) for best practices

---

## 🆘 Need Help?

- Check [README.md](README.md) for architecture details
- Review [TROUBLESHOOTING.md](.gemini/.../TROUBLESHOOTING.md)
- Open an issue on GitHub

---

**Happy coding! 🚀**
