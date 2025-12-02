"""
Group Orchestrator Service.

Coordinates all group-related services:
- Content moderation (check messages)
- Warning management (track violations)
- Message handling (quote-replies, context)
- Response delivery (auto-delete)

This is the main entry point for group message handling.
"""

import logging
from typing import Optional, Any

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.services.moderation import ContentModerator, WarningService
from telegram_bot.services.group.group_helper import GroupHelper
from telegram_bot.services.message_service import send_to_user
from utils.common import schedule_message_deletion

logger = logging.getLogger(__name__)


class GroupOrchestrator:
    """
    Orchestrates group message handling.
    
    Flow:
    1. Check moderation (single LLM call)
    2. If flagged: delete message, add warning, check ban
    3. If safe: extract context, process with agent
    4. Send auto-deleting response
    """
    
    AUTO_DELETE_DELAY = 30  # seconds
    
    def __init__(
        self,
        content_moderator: Optional[ContentModerator] = None,
        warning_service: Optional[WarningService] = None,
        group_helper: Optional[GroupHelper] = None,
        agent: Optional[Any] = None
    ):
        """
        Initialize the orchestrator with required services.
        
        Args:
            content_moderator: Service for content moderation
            warning_service: Service for tracking warnings
            group_helper: Helper for context extraction
            agent: AgentService for processing queries
        """
        self.moderator = content_moderator or ContentModerator()
        self.warning_service = warning_service or WarningService()
        self.helper = group_helper or GroupHelper()
        self.agent = agent
        
        logger.info("GroupOrchestrator initialized")
    
    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_message: str,
        user_id: int,
        user_profile: Optional[dict] = None,
        bot_username: str = ""
    ) -> None:
        """
        Handle ALL group messages.
        
        Flow:
        1. MODERATION: Check every message (delete abuse/spam)
        2. RESPONSE: Only if @mentioned
        
        Args:
            update: Telegram update object
            context: Bot context
            user_message: Original message text
            user_id: Telegram user ID
            user_profile: User's profile data
            bot_username: Bot's username for mention detection
        """
        chat_id = update.effective_chat.id
        username = update.effective_user.username or ""
        group_title = update.effective_chat.title or ""
        
        logger.info(f"━━━ GROUP MESSAGE ━━━")
        logger.info(f"📍 Group: '{group_title}' (chat_id={chat_id})")
        logger.info(f"👤 User: {user_id} (@{username})")
        logger.debug(f"📝 Message: '{user_message[:80]}...'")
        
        # === STEP 1: MODERATION (runs on ALL messages) ===
        # Strip bot mention before moderation to avoid false positives
        message_for_moderation = user_message
        if bot_username:
            message_for_moderation = user_message.replace(f"@{bot_username}", "").strip()
        
        logger.info(f"🔍 STEP 1: Running moderation check...")
        logger.debug(f"   Checking: '{message_for_moderation[:60]}...'")
        mod_result = await self.moderator.check(message_for_moderation)
        
        if mod_result.is_flagged:
            logger.warning(f"🚨 MESSAGE FLAGGED! Category: {mod_result.category}")
            logger.warning(f"   Raw response: {mod_result.raw_response}")
            await self._handle_violation(
                update, context, user_id, chat_id, username
            )
            return  # Stop processing
        
        logger.info(f"✅ STEP 1: Moderation passed")
        
        # === STEP 2: CHECK IF BOT IS MENTIONED ===
        is_mentioned = bot_username and f"@{bot_username}" in user_message
        logger.info(f"👀 STEP 2: Bot mentioned? {is_mentioned}")
        
        if not is_mentioned:
            logger.debug(f"⏭️ Not mentioned, exiting (moderation done)")
            return  # Not mentioned, moderation done, exit silently
        
        # Remove mention for cleaner processing
        if bot_username:
            user_message = user_message.replace(f"@{bot_username}", "").strip()
            logger.debug(f"📝 Message after removing mention: '{user_message}'")
        
        # === STEP 3: EXTRACT CONTEXT ===
        logger.info(f"📋 STEP 3: Extracting context...")
        group_context = self.helper.extract_from_group_name(group_title)
        logger.debug(f"   Group context: {group_context}")
        
        # Get context from quote-reply
        replied_text = self.helper.extract_quote_reply(update.message)
        logger.debug(f"   Quote-reply: {replied_text[:50] if replied_text else 'None'}")
        
        # Build enriched message
        enriched_message = self.helper.build_context_message(
            user_message=user_message,
            replied_text=replied_text,
            group_context=group_context
        )
        logger.debug(f"   Enriched message: '{enriched_message[:100]}...'")
        
        # === STEP 4: CHECK IF WE CAN RESPOND ===
        if not enriched_message:
            logger.info(f"❓ STEP 4: Empty message, sending help prompt")
            response = await self._send_auto_delete(
                update, context,
                "Hi! How can I help you? 💬"
            )
            return
        
        # Check if we have enough context
        has_context = self.helper.has_sufficient_context(
            user_message=user_message,
            group_context=group_context,
            user_profile=user_profile
        )
        logger.info(f"📊 STEP 4: Sufficient context? {has_context}")
        
        if not has_context:
            logger.info(f"❌ Insufficient context, redirecting to DM")
            response = await self._send_auto_delete(
                update, context,
                "💬 *Need more details!*\n\n"
                "Please DM me with your class and subject, "
                "or ask in full like: \"Class 12 AI sample papers\""
            )
            return
        
        # === STEP 5: PROCESS WITH AGENT ===
        logger.info(f"🤖 STEP 5: Processing with AgentService...")
        if self.agent:
            try:
                response = await self.agent.process(
                    user_message=enriched_message,
                    user_id=user_id,
                    user_profile=user_profile,
                    chat_type="group"
                )
                logger.info(f"✅ Agent response received ({len(response)} chars)")
                # Send response (NO auto-delete - keep helpful answers visible)
                await update.message.reply_text(response, parse_mode="Markdown")
                logger.info(f"📤 Response sent (permanent)")
            except Exception as e:
                logger.error(f"❌ Agent error in group: {e}", exc_info=True)
                await self._send_auto_delete(
                    update, context,
                    "Sorry, I encountered an error. Please try again."
                )
        else:
            logger.warning("⚠️ No agent configured for GroupOrchestrator")
    
    async def _handle_violation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        chat_id: int,
        username: str
    ) -> None:
        """
        Handle a content violation.
        
        1. Delete the offending message
        2. Add warning to user
        3. Send warning via DM
        4. Execute ban if threshold reached
        """
        logger.info(f"━━━ HANDLING VIOLATION ━━━")
        logger.info(f"👤 User: {user_id} (@{username})")
        logger.info(f"📍 Chat: {chat_id}")
        
        # Step 1: Delete the message
        logger.info(f"🗑️ Step 1: Deleting offending message...")
        try:
            await update.message.delete()
            logger.info(f"✅ Message deleted successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete message: {type(e).__name__}: {e}")
        
        # Step 2: Add warning
        logger.info(f"⚠️ Step 2: Adding warning to user...")
        warning_result = await self.warning_service.add_warning(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            reason="content_violation"
        )
        logger.info(f"📊 Warning count: {warning_result.warning_count}, should_ban: {warning_result.should_ban}")
        
        # Step 3: Send warning via DM
        logger.info(f"📨 Step 3: Sending warning DM...")
        try:
            await send_to_user(context, user_id, warning_result.message)
            logger.info(f"✅ Warning DM sent to user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ Could not send warning DM: {type(e).__name__}: {e}")
        
        # Step 4: Execute ban if needed
        if warning_result.should_ban:
            logger.info(f"🚫 Step 4: Executing BAN for user {user_id} in chat {chat_id}")
            ban_success = await self.warning_service.execute_ban(
                bot=context.bot,
                user_id=user_id,
                chat_id=chat_id
            )
            if ban_success:
                logger.info(f"✅ User {user_id} BANNED successfully")
            else:
                logger.error(f"❌ Ban FAILED for user {user_id} - check bot admin permissions!")
        else:
            logger.info(f"ℹ️ No ban needed (warning count below threshold)")
    
    async def _send_auto_delete(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str
    ) -> None:
        """
        Send a message that auto-deletes after delay.
        
        Args:
            update: Telegram update
            context: Bot context
            text: Message text to send
        """
        try:
            sent_message = await update.message.reply_text(
                text,
                parse_mode="Markdown"
            )
            
            # Schedule deletion
            schedule_message_deletion(
                bot=context.bot,
                chat_id=sent_message.chat_id,
                message_id=sent_message.message_id,
                delay=self.AUTO_DELETE_DELAY
            )
            
        except Exception as e:
            logger.error(f"Error sending auto-delete message: {e}")

