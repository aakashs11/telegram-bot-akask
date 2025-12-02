"""
Content Moderator Service.

Single LLM call for unified content moderation:
- Spam detection (links, promotions, scams)
- Abuse detection (any language including Hindi/Hinglish)
- Safety checks (threats, hate speech, harassment)

Replaces the previous 2-API-call system (LLM + OpenAI Moderation API)
with a single, more cost-effective gpt-4o-mini call.
"""

import logging
import asyncio
from dataclasses import dataclass
from typing import Optional

from utils.openai_client import get_client
from telegram_bot.prompts import PromptFactory

logger = logging.getLogger(__name__)


@dataclass
class ModerationResult:
    """
    Result of content moderation check.
    
    Attributes:
        is_flagged: Whether the message was flagged as inappropriate
        category: Category of violation (spam, abuse, threat, etc.)
        raw_response: Raw LLM response for debugging
    """
    is_flagged: bool
    category: str = ""
    raw_response: str = ""


class ContentModerator:
    """
    Unified content moderation using a single LLM call.
    
    Uses gpt-4o-mini with a simple binary (YES/NO) prompt to detect:
    - Spam: promotions, unauthorized t.me links, scams
    - Abuse: profanity, slurs, insults in ANY language (Hindi/Hinglish/English)
    - Safety: threats, hate speech, harassment, adult content
    
    Benefits over previous 2-API system:
    - 50% cost reduction (1 API call vs 2)
    - Better multilingual abuse detection
    - Simpler, unified logic
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """
        Initialize the content moderator.
        
        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.client = get_client()
        self.model = model
        logger.info(f"ContentModerator initialized with model: {model}")
    
    async def check(self, text: str) -> ModerationResult:
        """
        Check if a message is inappropriate.
        
        Args:
            text: The message text to check
            
        Returns:
            ModerationResult with is_flagged=True if inappropriate
        """
        if not text or not text.strip():
            return ModerationResult(is_flagged=False)
        
        try:
            # Load prompt from file via PromptFactory
            prompt_template = PromptFactory.get_content_moderation_prompt()
            prompt = prompt_template.format(text=text)
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.0  # Deterministic for consistent moderation
            )
            
            raw_response = response.choices[0].message.content.strip().upper()
            is_flagged = raw_response.startswith("YES")
            
            if is_flagged:
                logger.info(f"Message flagged: '{text[:50]}...' -> {raw_response}")
            
            return ModerationResult(
                is_flagged=is_flagged,
                category="content_violation" if is_flagged else "",
                raw_response=raw_response
            )
            
        except Exception as e:
            logger.error(f"Content moderation error: {e}")
            # Fail open - allow message but log error
            return ModerationResult(
                is_flagged=False,
                category="error",
                raw_response=str(e)
            )

