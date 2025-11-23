# 🔄 Development Workflow - Feature to Production

## 📋 Complete End-to-End Process

### 1️⃣ **Create Feature Branch**

```bash
cd /Users/aakash/Desktop/Youtube\ Repositories/telegram-bot-akask

# Always start from latest main
git checkout main
git pull origin main

# Create feature branch (use descriptive names)
git checkout -b feat/your-feature-name
# Examples: feat/new-tool, fix/bug-name, refactor/component-name
```

---

### 2️⃣ **Make Your Changes**

Edit code as needed, then:

```bash
# Check what changed
git status
git diff

# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: Description of what you did"
```

**Commit message format:**
- `feat:` - New features
- `fix:` - Bug fixes  
- `refactor:` - Code cleanup
- `docs:` - Documentation only

---

### 3️⃣ **Test Locally with DEV Bot**

#### Option A: Use the automation script (recommended)
```bash
./start_devtest.sh
```

This script automatically:
- Activates pipenv
- Stops any existing ngrok
- Starts fresh ngrok tunnel
- Sets webhook to DEV bot
- Runs the bot with hot reload

#### Option B: Manual testing
```bash
# Activate environment
pipenv shell

# Start ngrok in separate terminal
ngrok http 8000

# Copy ngrok URL, then run bot
NGROK_URL=https://xxxx.ngrok.io python main.py
```

**Test your DEV bot** (token ending in different numbers):
- Send messages to verify functionality
- Check terminal logs for errors
- Test all affected features

---

### 4️⃣ **Push Feature Branch**

```bash
# Push to GitHub
git push -u origin feat/your-feature-name

# If you made more changes
git add .
git commit -m "fix: Additional changes"
git push
```

---

### 5️⃣ **Create Pull Request**

1. Go to: https://github.com/aakashs11/telegram-bot-akask
2. Click "Compare & pull request"
3. **Review Cursor's bug detector** - Fix critical bugs
4. Fill in PR description
5. Click "Create pull request"

**DO NOT MERGE YET!**

---

### 6️⃣ **Pre-Merge Checklist**

Run through this checklist:

```bash
# Check for missing dependencies
pipenv check

# Verify requirements.txt is up to date
pipenv requirements > requirements.txt

# Check for secrets in code
git diff main...feat/your-feature-name | grep -i "sk-" || echo "✅ No secrets found"

# Test imports work
python -c "from telegram_bot.application import application; print('✅ Imports OK')"
```

---

### 7️⃣ **Merge to Main**

On GitHub:
1. Review Cursor's feedback one last time
2. Click "Merge pull request"
3. Click "Confirm merge"
4. Delete the feature branch (optional)

---

### 8️⃣ **Deploy to Production**

#### Automated Script (simplest):

```bash
# Pull latest main locally
git checkout main
git pull origin main

# Run deployment script
./deploy.sh
```

The `deploy.sh` script will:
- Deploy to Cloud Run
- Update cloud-run-url secret
- Configure PROD bot webhook
- Show verification info

#### Monitor Deployment:

```bash
# Watch logs in real-time
gcloud run services logs tail telegram-bot --region asia-south1

# Check deployment status
gcloud run services describe telegram-bot --region asia-south1
```

---

### 9️⃣ **Verify Production Bot**

**Test PROD bot** (token `PROD_BOT_TOKEN_HERE`):

```bash
# Check webhook
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq

# Expected: URL points to Cloud Run, pending_update_count = 0
```

**Manual tests:**
1. "I need Class 10 AI notes" → Should return folder link
2. "Show me Python videos" → Should return 5 videos
3. "Update my profile to Class 12 CS" → Should confirm update

---

## 🛠️ Automation Scripts Reference

### `./start_devtest.sh`
**Purpose**: Local development with DEV bot
**What it does**:
- Activates pipenv
- Kills existing ngrok processes
- Starts new ngrok tunnel
- Sets DEV bot webhook
- Runs bot with auto-reload

**Usage**:
```bash
./start_devtest.sh
```

### `./deploy.sh`
**Purpose**: Production deployment to Cloud Run
**What it does**:
- Deploys from source to Cloud Run
- Updates cloud-run-url secret
- Configures PROD bot webhook
- Shows success message with URL

**Usage**:
```bash
./deploy.sh
```

---

## 🔍 Common Issues & Fixes

### Issue: "ModuleNotFoundError" in Cloud Run

**Cause**: Missing dependency in `requirements.txt`

**Fix**:
```bash
# Generate fresh requirements
pipenv requirements > requirements.txt

# Commit and push
git add requirements.txt
git commit -m "fix: Update requirements.txt"
git push origin main

# Redeploy
./deploy.sh
```

### Issue: Secrets not loading in production

**Cause**: Service account lacks Secret Manager permissions

**Fix**:
```bash
SA_EMAIL="telegram-bot-user@telegram-bot-akask.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding telegram-bot-akask \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

### Issue: Bot not responding after deployment

**Fix**:
```bash
# Check logs
gcloud run services logs read telegram-bot --region asia-south1 --limit=50

# Restart service
gcloud run services update telegram-bot --region asia-south1

# Verify webhook
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

---

## 📝 Quick Reference Commands

```bash
# Development
git checkout -b feat/feature-name        # Create branch
./start_devtest.sh                       # Test locally
git add . && git commit -m "feat: msg"   # Commit
git push -u origin feat/feature-name     # Push

# Deployment
git checkout main && git pull            # Get latest
./deploy.sh                              # Deploy
gcloud run services logs tail...         # Monitor

# Debugging
gcloud run services logs read...         # View logs
gcloud run services describe...          # Check status
curl "https://api.telegram.org/bot.../getWebhookInfo"  # Verify webhook
```

---

## 🎯 Best Practices

1. **Always create feature branches** - Never commit directly to main
2. **Test with DEV bot first** - Use `start_devtest.sh`
3. **Keep commits focused** - One feature/fix per commit
4. **Update requirements.txt** - Run `pipenv requirements > requirements.txt`
5. **Check Cursor's feedback** - Fix critical bugs before merging
6. **Monitor after deployment** - Check logs and test PROD bot
7. **Keep secrets in Secret Manager** - Never commit API keys

---

## 📊 Typical Timeline

| Step | Time | Notes |
|------|------|-------|
| Create branch & code | Variable | Your development time |
| Local testing | 5-10 min | Using `start_devtest.sh` |
| Push & create PR | 2 min | Including Cursor review |
| Fix bugs from review | 10-30 min | If needed |
| Merge to main | 1 min | One click |
| Deploy to Cloud Run | 5-8 min | Using `./deploy.sh` |
| Verify production | 3-5 min | Test + check logs |
| **Total (excluding coding)** | **~30 min** | From push to verified deploy |

---

## 🚨 Emergency Rollback

If deployment breaks production:

```bash
# List revisions
gcloud run revisions list --service=telegram-bot --region=asia-south1

# Rollback to previous
gcloud run services update-traffic telegram-bot \
  --region=asia-south1 \
  --to-revisions=telegram-bot-00XXX=100

# Verify bot works
# Fix issue locally, then redeploy
```

---

## ✅ Deployment Success Checklist

After every deployment, verify:
- [ ] Cloud Run service shows "Serving"
- [ ] Webhook URL points to Cloud Run
- [ ] `pending_update_count` is 0
- [ ] PROD bot responds to test message
- [ ] No errors in logs (last 20 lines)
- [ ] Response time < 5 seconds

If all checkboxes pass: **Deployment successful!** 🎉
