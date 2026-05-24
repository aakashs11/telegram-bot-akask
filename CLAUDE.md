# CLAUDE.md — Codebase context for Claude Code

## Active branch: `codex/platformization`

This branch introduces a platform-neutral `ChatRuntime` layer (see `telegram_bot/runtime/`). Telegram-specific parsing and delivery live in `telegram_bot/adapters/telegram_adapter.py`. All message routing, moderation, and agent calls go through `ChatRuntime.handle()`.

---

## Recent fixes on this branch

### Profile defaults fix (`fix/profile-defaults-notes-tool` → merged into `codex/platformization`)

**Problem:** 14% of responses were "please specify your class/subject" even when the student had a complete profile set. A bare message like "notes" would trigger a clarification question instead of fetching notes.

**Root causes found and fixed:**

1. **`telegram_bot/prompts/prompt_factory.py`**
   - Bug: `if user_profile:` injected the profile section even when `current_class` and `preferred_subject` were both `None`. Every new user gets an auto-created profile with both fields as `None`, so a non-empty dict alone is not sufficient.
   - Fix: Only inject profile section when both `current_class` and `preferred_subject` are actually set.

2. **`telegram_bot/prompts/agent_system.md`**
   - Bug: `get_notes` rule said "If class/subject missing, ASK user politely" — model read "missing from the message" and asked even with a full profile.
   - Fix: Rule now says check profile first; only ask if BOTH the message/history AND the profile lack class or subject. Added `Profile Defaults` critical rule scoped to profiles where both values are confirmed set.

3. **`telegram_bot/prompts/profile_section.md`**
   - Bug: Weak single-line instruction ("You MUST use these values") was overridden by the more specific per-tool rule.
   - Fix: Replaced with explicit trigger→action table for all resource types (Notes, Books, Syllabus, Sample Papers) and a hard `DO NOT ask` guard.

**Key insight:** `profile_section.md` is only injected when both class and subject are confirmed set (after the `prompt_factory.py` fix), so the aggressive "do not ask" instruction is safe — it will never appear for users with incomplete profiles.

---

## Eval coverage

- `evals/chat_runtime_eval.py` — 20 cases, uses `FakeAgent` (no real API calls). Tests routing logic only.
- `evals/moderation_eval.py` — 75 cases, makes real API calls to `ContentModerator`.
- **Gap:** No real-API eval for profile defaults or agent prompt behavior. A prompt-level eval (similar to `moderation_eval.py`) should be added post-ship.

---

## Dev setup

- Venv lives in `/home/jimmy/ASK AI/` (parent dir, not in repo): `/home/jimmy/ASK AI/venv`
- Run evals: `TELEGRAM_BOT_TOKEN=dummy OPENAI_API_KEY=dummy /home/jimmy/ASK\ AI/venv/bin/python -m evals.chat_runtime_eval`
- Dev bot script: `./start_devtest.sh` (starts ngrok + bot, regex broadened to match any ngrok TLD)
