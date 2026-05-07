import logging
import os
import requests
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from telegram import Update
from telegram_bot.application import application  # Import your telegram application instance
from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    CLOUD_RUN_URL,
    get_sheet,
)


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set the Telegram webhook if CLOUD_RUN_URL is provided
    if CLOUD_RUN_URL:
        webhook_url = f"{CLOUD_RUN_URL}/webhook"
        webhook_payload = {"url": webhook_url}
        if TELEGRAM_WEBHOOK_SECRET:
            webhook_payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET
        else:
            logger.warning("TELEGRAM_WEBHOOK_SECRET is not set; webhook requests cannot be authenticated.")

        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json=webhook_payload,
        )
        if response.status_code == 200:
            logger.info(f"Webhook set successfully: {webhook_url}")
        else:
            logger.error(f"Failed to set webhook: {response.text}")
    else:
        logger.warning(
            "CLOUD_RUN_URL is not set. The webhook will need to be configured manually."
        )

    # Lazily initialize Google Sheet and place in bot_data for handlers to use
    try:
        sheet = get_sheet()
        if sheet is not None:
            application.bot_data["sh"] = sheet
            logger.info("Google Sheet handle registered in application.bot_data.")
        else:
            logger.info("Google Sheet unavailable; proceeding without logging.")
    except Exception as exc:
        logger.warning(f"Failed to prepare Google Sheet: {exc}")
    yield  # Allow the application to run

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}

@app.post("/webhook")
async def handle_webhook(request: Request):
    if TELEGRAM_WEBHOOK_SECRET:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header_secret != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        # Ensure the Telegram application is initialized before processing updates
        await application.initialize()

        # Process the incoming webhook update
        update = Update.de_json(await request.json(), application.bot)
        await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Error handling webhook") 
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
