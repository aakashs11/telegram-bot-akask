"""
Moderation Service.
Checks user messages against OpenAI's Moderation API to detect spam, hate speech, etc.
"""

import logging
from utils.openai_client import get_client
import json

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ModerationResult:
    is_flagged: bool
    categories: List[str]
    score: float
    reason: str = ""

class ModerationService:
    """
    Service to check messages for inappropriate content using:
    1. GPT-4o-mini for context-aware spam detection (cheap, fast, smart).
    2. OpenAI Moderation API for safety (hate, violence, etc.).
    """
    
    def __init__(self):
        self.client = get_client()

    async def check_message(self, text: str) -> ModerationResult:
        """
        Check if a message is safe.
        1. Check Spam (GPT-4o-mini).
        2. Check Safety (OpenAI Moderation API).
        
        Args:
            text: The user's message text.
            
        Returns:
            ModerationResult object with details.
        """
        if not text:
            return ModerationResult(False, [], 0.0)
            
        # 1. Check Spam (GPT-4o-mini)
        spam_result = await self._check_spam_llm(text)
        if spam_result.is_flagged:
            logger.info(f"Message flagged as spam by LLM: {spam_result.reason}")
            return spam_result

        try:
            # 2. Check OpenAI Moderation API (Safety)
            # Run in thread pool since openai client is sync
            import asyncio
            
            response = await asyncio.to_thread(
                self.client.moderations.create,
                input=text
            )
            
            result = response.results[0]
            
            # Extract flagged categories
            flagged_categories = [
                cat for cat, flagged in result.categories.model_dump().items() if flagged
            ]
            
            # Get highest category score
            scores = result.category_scores.model_dump()
            max_score = max(scores.values()) if scores else 0.0
            
            return ModerationResult(
                is_flagged=result.flagged,
                categories=flagged_categories,
                score=max_score
            )
            
        except Exception as e:
            logger.error(f"Error in moderation check: {e}")
            # Fail open but log error
            return ModerationResult(False, ["error"], 0.0)

    async def _check_spam_llm(self, text: str) -> ModerationResult:
        """
        Uses GPT-4o-mini to detect spam with high accuracy and low cost.
        """
        from telegram_bot.prompts import PromptFactory
        system_prompt = PromptFactory.get_spam_detection_prompt()
        
        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            if data.get("is_spam"):
                return ModerationResult(
                    is_flagged=True,
                    categories=["spam/llm"],
                    score=1.0,
                    reason=data.get("reason", "Detected by LLM")
                )
                
        except Exception as e:
            logger.error(f"LLM Spam check failed: {e}")
            
        return ModerationResult(False, [], 0.0)
