import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from telegram_bot.services.moderation_service import ModerationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_moderation():
    service = ModerationService()
    
    test_cases = [
        {
            "text": "Hello, how are you?",
            "should_flag": False,
            "desc": "Safe message"
        },
        {
            "text": "Class 10 PW project 45 free link https://t.me/ProjectSpamBot",
            "should_flag": True,
            "expected_category": "spam/llm",
            "desc": "Spam: Free link t.me (Generic)"
        },
        {
            "text": "class 10 pw project 45 free link https://t.me/Project_45_Crash_Course_Class_10",
            "should_flag": True,
            "expected_category": "spam/llm",
            "desc": "Spam: User Specific Example"
        },
        {
            "text": "Hey guys, is this project link free to use? I need it for my assignment.",
            "should_flag": False,
            "desc": "Safe: Contextual question about free link (Should NOT be flagged)"
        },
        {
            "text": "URGENT! Get your class project for free here! Limited time offer!",
            "should_flag": True,
            "expected_category": "spam/llm",
            "desc": "Spam: Promotional urgency"
        }
    ]
    
    print("🧪 Starting LLM Moderation Tests (GPT-4o-mini)...")
    
    for case in test_cases:
        print(f"\nTesting: {case['desc']}")
        print(f"Input: '{case['text']}'")
        
        result = await service.check_message(case['text'])
        
        print(f"Result: Flagged={result.is_flagged}, Categories={result.categories}, Reason={result.reason}")
        
        if result.is_flagged != case['should_flag']:
            print(f"❌ FAILED: Expected flagged={case['should_flag']}, got {result.is_flagged}")
        elif case['should_flag'] and case['expected_category'] not in result.categories:
             print(f"❌ FAILED: Expected category {case['expected_category']}, got {result.categories}")
        else:
            print("✅ PASSED")

if __name__ == "__main__":
    asyncio.run(test_moderation())
