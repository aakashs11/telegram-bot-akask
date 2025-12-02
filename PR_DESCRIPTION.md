# 🛡️ Group Moderation System

## Summary

This PR introduces a comprehensive group moderation system that detects spam, abuse (multi-language including Hindi/Hinglish), and safety violations with a single LLM call. It includes an automated warning and ban system.

## 🎯 Problem

- No moderation for group messages
- Hindi abuses were not being detected
- Previous 2-API system (LLM + OpenAI Moderation) was costly
- No warning/ban mechanism for repeat offenders

## ✨ Solution

### New Architecture

```
handlers.py (thin router)
    ├── Private Chat → AgentService + ContentModerator
    └── Group Chat → GroupOrchestrator
                        ├── ContentModerator (single LLM call)
                        ├── WarningService (Google Sheets)
                        └── GroupHelper (context extraction)
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Unified Moderation** | Single `gpt-4o-mini` call detects spam + abuse + safety (50% cost reduction) |
| **Multi-language Abuse** | Catches Hindi, Hinglish, English profanity |
| **2-Strike Ban Policy** | 1st violation = warning, 2nd = permanent ban |
| **Smart Auto-delete** | Only helper messages auto-delete; actual answers stay visible |
| **Quote-reply Context** | Bot uses replied message as context |
| **Group Name Context** | Extracts class/subject from group title |
| **Comprehensive Logging** | Step-by-step logs with emojis for debugging |

## 📁 Files Changed

### New Files
- `telegram_bot/services/moderation/content_moderator.py` - Unified content moderation
- `telegram_bot/services/moderation/warning_service.py` - Warning tracking & bans
- `telegram_bot/services/group/group_orchestrator.py` - Group message coordination
- `telegram_bot/services/group/group_helper.py` - Context extraction
- `telegram_bot/prompts/content_moderation.md` - Moderation prompt
- `evals/moderation_eval.py` - 75+ test cases for moderation accuracy

### Modified Files
- `telegram_bot/handlers.py` - Refactored as thin routing layer
- `telegram_bot/application.py` - Initialize new services
- `telegram_bot/prompts/prompt_factory.py` - Added moderation prompt loader
- `README.md` - Updated docs, quickstart, architecture diagram

### Deleted Files (Cleanup)
- `utils/intent.py`, `utils/screening.py` - Unused
- `functions/notes.py`, `data/index.json` - Legacy
- `telegram-bot-akask.git/` - Duplicate folder

## 🧪 Testing

Run moderation evaluation:
```bash
python -m evals.moderation_eval
```

Test cases include:
- 10 spam patterns (t.me links, scams)
- 20 Hindi severe abuse (Roman script)
- 10 Hindi mild insults
- 10 Hindi Devanagari script
- 10 English abuse
- 15 safe messages (should NOT flag)

## ⚠️ Warning Flow

```
1st Violation → ⚠️ WARNING (DM) + Message Deleted
2nd Violation → 🚫 BANNED + Removed from Group
```

## 📋 Checklist

- [x] Single LLM call for all moderation
- [x] Hindi/Hinglish abuse detection
- [x] Warning system with Google Sheets storage
- [x] Auto-ban after 2 violations
- [x] Message deletion for violations
- [x] Auto-delete group responses
- [x] Comprehensive logging
- [x] Evaluation script with 75+ test cases
- [x] Updated README documentation
- [x] Cleaned up unused files

## 🚀 Deployment Notes

1. Bot needs **admin permissions** in groups (delete messages, ban users)
2. Google Sheets needs "Warnings" tab with columns: `user_id`, `chat_id`, `username`, `warning_count`, `reason`, `timestamp`, `banned`

