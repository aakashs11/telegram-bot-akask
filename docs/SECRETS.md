# Local development credentials

> **New developer?** Start with **[ONBOARDING.md](ONBOARDING.md)** — setup, platformization branch, and PR workflow in one place. This file covers credential details only.

This project loads configuration from a `.env` file and `service_account.json` in the repository root. Those files are gitignored and must never be committed.

Production deployments use **Google Cloud Secret Manager** (see `deploy.sh`). Local development uses a shared **dev** credential set, distributed outside the repository.

---

## For new developers

You need two files in the project root before running the bot:

| File | Purpose |
|------|---------|
| `.env` | API keys and resource IDs |
| `service_account.json` | Google Sheets and Drive access |

### 1. Obtain credentials

Ask the project maintainer for:

- A completed `.env` file (or the values to paste into one), and  
- `service_account.json`

Credentials are shared through a **private channel** (Bitwarden secure note, Bitwarden Send, or another approved secret-sharing method). Do not request or store them in Slack, email, or GitHub.

### 2. Install files

```bash
cd telegram-bot-akask
cp .env.example .env   # only if you received values separately
# Paste maintainer-provided values into .env, or replace .env with the file you received

# Place service_account.json in the project root
chmod 600 .env service_account.json
```

Confirm `.env` uses **`SHEET_ID`** (not `GOOGLE_SHEET_ID`). The application reads `SHEET_ID` in `config/settings.py`.

### 3. Prerequisites

- Python 3.12 and [pipenv](https://pipenv.pypa.io/)
- [ngrok](https://ngrok.com/) (for local webhooks)
- Repository clone and `pipenv install`

See `QUICKSTART.md` for full setup steps.

### 4. Run the dev bot

```bash
./start_devtest.sh
```

Message the **development** Telegram bot (not production). Only one developer should run `start_devtest.sh` against a given dev bot at a time, because the webhook is pointed at whoever’s ngrok tunnel is active last.

### 5. Verify (optional)

```bash
pipenv run python -m evals.chat_runtime_eval
pipenv run python -m evals.moderation_eval --verbose   # uses OpenAI; incurs cost
```

---

## Required environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Token for the **development** bot from [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | Yes | OpenAI API key for the agent and moderation |
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 key |
| `SHEET_ID` | Yes | Google Sheet ID for profiles and moderation logs |
| `DRIVE_FOLDER_ID` | Yes | Root Drive folder ID for study materials |
| `NGROK_URL` | No | Filled automatically by `start_devtest.sh` |

Google access: the service account email inside `service_account.json` must have access to the Sheet and Drive folder above (configured in Google Cloud / sharing settings by the maintainer).

---

## For maintainers: onboarding a developer

### Prepare a dev `.env`

1. Copy `.env.example` to a local `.env` with **dev-only** values (never production tokens).
2. Ensure all required variables in the table above are set.
3. Use `SHEET_ID` consistently.

Example layout:

```bash
# Development bot — not production
TELEGRAM_BOT_TOKEN=<dev-bot-token>
OPENAI_API_KEY=<key>
YOUTUBE_API_KEY=<key>
SHEET_ID=<sheet-id>
DRIVE_FOLDER_ID=<folder-id>
NGROK_URL=
```

### Share credentials securely

Send the new developer:

1. The `.env` contents (as a file or via Bitwarden secure note / Send)  
2. `service_account.json` (same channel or separate Send with expiry)  
3. The dev bot’s Telegram **@username** so they know which bot to test  
4. A link to `QUICKSTART.md` and `DEVELOPMENT_WORKFLOW.md`

**Do not** commit `.env` or `service_account.json`. **Do not** share production Cloud Run secrets or the production bot token for local work.

### Optional: Bitwarden Secrets Manager (CLI)

You can store dev credentials in Secrets Manager and hand them off with the CLI. **Developers still use `.env` + `service_account.json` locally** — `bws` is only for upload/export, not for running the bot.

**Upload from your machine** (already done if you ran `populate_bws_dev_secrets.sh`):

```bash
export BWS_ACCESS_TOKEN='<your-write-token>'
./scripts/populate_bws_dev_secrets.sh
```

`SERVICE_ACCOUNT_JSON_B64` holds the same content as `service_account.json`, encoded so it can live in Secrets Manager.

**New developer: one-time download** (read-only machine account token + project id):

```bash
export BWS_ACCESS_TOKEN='<read-only-token>'
export BWS_PROJECT_ID='33403fe4-c585-4a77-ace7-b4510082ad50'

cd telegram-bot-akask
./scripts/export_dev_env_from_bws.sh
pipenv install
./start_devtest.sh
```

Or manually:

```bash
bws secret list "$BWS_PROJECT_ID" --output env | grep -v '^SERVICE_ACCOUNT_JSON_B64=' > .env
# Decode service account (macOS/Linux):
bws secret get <SERVICE_ACCOUNT_JSON_B64_SECRET_ID> --output json | python3 -c "
import json, sys, base64, pathlib
s = json.load(sys.stdin)
pathlib.Path('service_account.json').write_bytes(base64.b64decode(s['value']))
"
chmod 600 .env service_account.json
```

After export, he does **not** need `bws` again unless you rotate secrets.

### Access and safety

- Grant **read-only** access where possible (e.g. separate Bitwarden machine account per developer).
- Rotate keys if a credential is exposed or a developer offboards.
- Add the developer’s Telegram user ID to `ADMIN_USER_IDS` in `config/settings.py` only if they need admin/moderation bypass behavior during testing.

---

## Production credentials

Production secrets live in GCP Secret Manager for project `telegram-bot-akask`. Deployment is documented in `DEVELOPMENT_WORKFLOW.md` and performed with `./deploy.sh`. Local `.env` files are not used on Cloud Run.
