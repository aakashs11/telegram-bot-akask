from telegram import Update
from telegram.ext import ContextTypes
from utils.common import append_to_history
from utils.formatting import escape_markdown
from utils.intent import classify_intent
from config.settings import TELEGRAM_BOT_TOKEN  # noqa

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I am Akask.ai, your study buddy."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, sh=None):
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or ""
    # Prefer settings-provided sheet; if missing, try application bot_data; else None
    if sh is None:
        try:
            from config.settings import sh as settings_sh  # type: ignore
            sh = settings_sh
        except Exception:
            sh = context.application.bot_data.get("sh") if hasattr(context, "application") else None

    output = await classify_intent(user_message, user_id, sh)
    response = escape_markdown(output["final_output"])
    await update.message.reply_text(response, parse_mode="MarkdownV2")

    # Log to sheet if needed:
    from utils.gspread_logging import log_to_sheet
    if sh is not None:
        log_to_sheet(sh, user_id, username, user_message, output["output_screener"], output["output_intent"], output["output_entitites"], output["final_output"])
