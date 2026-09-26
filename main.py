import asyncio
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
    DATABASE_URL,
    DB_MAX_OVERFLOW,
    DB_POOL_SIZE,
    DB_POOL_TIMEOUT_SECONDS,
    INTERACTION_LOG_MODE,
    INTERACTION_WRITE_TIMEOUT_SECONDS,
    get_sheet,
)
from telegram_bot.infrastructure.database import Database
from telegram_bot.infrastructure.postgres_interaction_repository import (
    PostgresInteractionRepository,
)
from telegram_bot.infrastructure.sheets_interaction_repository import (
    SheetsInteractionRepository,
)
from telegram_bot.services.interaction_logging_service import (
    InteractionLoggingService,
)


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = None

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

    sheet_repository = None
    if INTERACTION_LOG_MODE in {"sheet", "dual"}:
        sheet_repository = SheetsInteractionRepository(get_sheet)

    postgres_repository = None
    database_ready = None
    if INTERACTION_LOG_MODE in {"postgres", "dual"}:
        if DATABASE_URL:
            try:
                database = Database(
                    DATABASE_URL,
                    pool_size=DB_POOL_SIZE,
                    max_overflow=DB_MAX_OVERFLOW,
                    pool_timeout_seconds=DB_POOL_TIMEOUT_SECONDS,
                )
                postgres_repository = PostgresInteractionRepository(
                    database.engine
                )
                try:
                    database_ready = await asyncio.wait_for(
                        database.healthcheck(),
                        timeout=DB_POOL_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    database_ready = False
            except Exception as exc:
                database_ready = False
                database = None
                postgres_repository = None
                logger.error(
                    "Interaction database initialization failed",
                    extra={
                        "mode": INTERACTION_LOG_MODE,
                        "error_type": type(exc).__name__,
                    },
                )
            if not database_ready and postgres_repository is not None:
                # Startup remains fail-open. Later writes still use the engine
                # so a transient database outage can recover without a restart.
                logger.error(
                    "Interaction database health check failed",
                    extra={"mode": INTERACTION_LOG_MODE},
                )
        else:
            database_ready = False
            logger.error(
                "DATABASE_URL is required for the configured interaction log mode",
                extra={"mode": INTERACTION_LOG_MODE},
            )

    logging_service = InteractionLoggingService(
        mode=INTERACTION_LOG_MODE,
        sheet_repository=sheet_repository,
        postgres_repository=postgres_repository,
        write_timeout_seconds=INTERACTION_WRITE_TIMEOUT_SECONDS,
    )
    application.bot_data["interaction_logging_service"] = logging_service
    app.state.interaction_database = database
    logger.info(
        "Interaction logging initialized: mode=%s database_ready=%s",
        INTERACTION_LOG_MODE,
        database_ready,
        extra={
            "mode": INTERACTION_LOG_MODE,
            "database_ready": database_ready,
        },
    )

    try:
        yield  # Allow the application to run
    finally:
        application.bot_data.pop("interaction_logging_service", None)
        if database is not None:
            await database.close()
            logger.info("Interaction database connections closed")

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
