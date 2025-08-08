##
## Telegram Study Assistant Bot (Windows)

### Overview
This project is a FastAPI-based Telegram webhook service that helps students quickly find notes and videos. It uses the OpenAI Responses API for intent handling and decision-making, Google Sheets for optional logging, and (optionally) YouTube Data API for video search.

### Architecture
- **FastAPI** entrypoint: `main.py` exposes `/webhook` (Telegram) and sets webhook on startup when `CLOUD_RUN_URL` is provided.
- **Telegram bot**: `telegram_bot/application.py` builds the bot and registers handlers in `telegram_bot/handlers.py`.
- **Intent & Screening**:
  - `utils/screening.py` screens messages (Responses API) and returns JSON `{is_valid, comments}`.
  - `utils/intent.py` decides an action via Responses API (JSON control: `get_notes`, `get_videos`, or `reply`).
- **Tools**:
  - `functions/notes.py`: reads `data/index.json` and formats note links.
  - `functions/videos.py`: searches YouTube for topic-specific videos.
- **Utilities**: formatting, history, and Google Sheets logging.

### Requirements (Windows)
- Python 3.10+
- A Telegram bot token (create via BotFather) — use a separate DEV bot for testing.
- OpenAI API key.
- Optional: Google Cloud credentials for Sheets logging (ADC), YouTube API key.
- Optional for deployment: Google Cloud SDK and a GCP project.

### Environment variables
Create a `.env` file in the project root for local development (values are examples):

```
TELEGRAM_BOT_TOKEN=123456:ABC-your-dev-bot-token
OPENAI_API_KEY=sk-xxxx
YOUTUBE_API_KEY=AIza-xxxx (optional)
SHEET_ID=1-1Y4O4RAa-XgtAcGB_tEzXE3dta8pYxCgzj5o9FRqM0 (optional)
CLOUD_RUN_URL= (leave empty for local)
# Optional overrides
INDEX_PATH=C:\\Users\\you\\path\\to\\telegram-bot\\data\\index.json
```

Notes:
- `SHEET_ID` is optional. If credentials are not found, logging is skipped safely.
- `INDEX_PATH` overrides the default `data/index.json` path. This is useful on Windows.

### Local setup and run (Windows, cmd.exe)
1) Create and activate a virtual environment, install dependencies
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Run the FastAPI app
```
python -m uvicorn main:app --host 0.0.0.0 --port 8080
```

3) Expose locally via ngrok
```
ngrok http 8080
```
Copy the HTTPS forwarding URL shown by ngrok, for example: `https://abcd-1234.ngrok.io`.

4) Set the Telegram webhook for your DEV bot
```
curl "https://api.telegram.org/bot<DEV_BOT_TOKEN>/setWebhook?url=https://abcd-1234.ngrok.io/webhook"
```

5) Test in the Telegram app (DEV bot)
- Ask for notes: the bot should request missing details (class, subject, type) and return formatted links.
- Ask for topic-based videos: the bot should return a short list of links.
- Replies are short and MarkdownV2-safe.

6) Remove webhook when done (optional)
```
curl "https://api.telegram.org/bot<DEV_BOT_TOKEN>/deleteWebhook"
```

### Verify it’s wired correctly (local)
- Check the app is up: open `http://localhost:8080/` and see `{ "message": "Welcome to the FastAPI application!" }`
- Check webhook status:
```
curl "https://api.telegram.org/bot<DEV_BOT_TOKEN>/getWebhookInfo"
```
Should show your current public URL ending with `/webhook` and `last_error_message` should be empty.

### Common Windows issues (local)
- Port already in use (only one server per port):
```
netstat -aon | findstr :8080
taskkill /PID <PID_FROM_PREVIOUS_COMMAND> /F
```
Re-run: `python -m uvicorn main:app --host 0.0.0.0 --port 8080`
- `ngrok` not recognized: download for Windows and run with full path, or add to PATH and open a new terminal.
- Google Sheets 403: either grant the service account access to the sheet or ignore (logging is optional and safely disabled).

### Google Sheets logging (optional)
The app tries to initialize Google Sheets lazily on startup. If ADC isn’t configured, it proceeds without logging.

To enable on Windows using a service account JSON:
```
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json
```
Then ensure the service account has access to the spreadsheet specified by `SHEET_ID`.

### Data index for notes
- The bot reads from `data/index.json` by default.
- On Windows, you can override with `INDEX_PATH`:
```
set INDEX_PATH=C:\Users\you\path\to\telegram-bot\data\index.json
```
Structure is a nested object by class → subject → type → title → URL.

### OpenAI Responses API (how it’s used)
- Client: `utils/openai_client.py` initializes the official SDK and converts chat history into Responses format.
- Screening: `utils/screening.py` calls `client.responses.create(..., response_format={"type":"json_object"})` and parses `response.output_text`.
- Intent: `utils/intent.py` sends the conversation (with a concise system prompt) and receives a JSON decision:
  - `{ "action": "get_notes" | "get_videos" | "reply", "arguments": {...}, "reply": "..." }`
- Edit the system prompt in `utils/intent.py` to change behavior and policies.

### Zero-downtime deployment with Cloud Run (recommended)
Use two Cloud Run services:
- `telegram-bot-dev` (DEV token, from `cloudbuild-dev.yaml`)
- `telegram-bot` (PROD token, from `cloudbuild.yaml`)

Dev deploy (from project root):
```
gcloud builds submit --config cloudbuild-dev.yaml --project <PROJECT_ID>
```
Set the DEV webhook to the service URL (found in the Cloud Run console or `gcloud run services describe`):
```
curl "https://api.telegram.org/bot<DEV_BOT_TOKEN>/setWebhook?url=https://<dev-service>.run.app/webhook"
```

Prod deploy:
```
gcloud builds submit --config cloudbuild.yaml --project <PROJECT_ID>
```
For no cold starts and smooth rollouts:
```
gcloud run services update telegram-bot --region asia-south1 --min-instances 1 --project <PROJECT_ID>
```

Configure Cloud Run environment variables (Console → Cloud Run → Service → Edit & Deploy → Variables):
- `TELEGRAM_BOT_TOKEN` (dev/prod token per service)
- `OPENAI_API_KEY`
- `YOUTUBE_API_KEY` (optional)
- `SHEET_ID` (optional)
 - `CLOUD_RUN_URL` (optional; when set, the app auto-sets the webhook on startup)

### Verify it’s wired correctly (Cloud Run)
- Get service URL from Cloud Run. If `CLOUD_RUN_URL` is set, the webhook is auto-configured on startup. Otherwise set manually:
```
curl "https://api.telegram.org/bot<DEV_OR_PROD_BOT_TOKEN>/setWebhook?url=https://<service>.run.app/webhook"
curl "https://api.telegram.org/bot<DEV_OR_PROD_BOT_TOKEN>/getWebhookInfo"
```
- Send a message to the bot; check logs:
```
gcloud logs tail --project <PROJECT_ID> --billing-project <PROJECT_ID> --resource=cloud_run_revision --service=<SERVICE_NAME> --region=asia-south1
```

### Branching and CI
- Use two branches: `dev` → deploys to `telegram-bot-dev`, `main` → deploys to prod.
- Configure Cloud Build triggers per branch to run the respective YAML.
- Add lint/type checks over time (e.g., `ruff`, `mypy`) and a small test suite.

### Enhancements & evaluation (optional roadmap)
- Model controls via env (add to `.env` and wire through Responses API call): `MODEL_NAME`, `TEMPERATURE`, `MAX_TOKENS`.
- Retrieval: add a `functions/retrieve.py` and an ingest pipeline to index PDFs into a local vector store; route “explain” queries to retriever.
- Evaluation harness: `evaluation/run_eval.py` with a small dataset (`data/eval/qa.jsonl`) measuring Recall@k and response quality.
- Observability: add structured logging with `update_id`, request timing, tool choice, token counts.

### Troubleshooting (Windows)
- 400 Bad Request on sendMessage: ensure Markdown is valid; the code uses `escape_markdown` for safety. If you hand-edit responses, escape MarkdownV2.
- Webhook not firing: verify ngrok URL is HTTPS and the webhook URL matches `/webhook` exactly. Re-run the `setWebhook` command.
- Sheets errors: if you want logging, set `GOOGLE_APPLICATION_CREDENTIALS` and ensure the service account has access to `SHEET_ID`. Otherwise logging is skipped.
- `index.json` not found: set `INDEX_PATH` to your Windows path or keep the file under `data/index.json`.

### License
Personal/educational use. Add a license if you plan to distribute.


