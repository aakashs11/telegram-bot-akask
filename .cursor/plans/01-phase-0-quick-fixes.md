# Phase 0: Quick Fixes

**Duration:** Day 1  
**Dependencies:** None  
**Technology:** No new tech — Python code fixes only  

---

## User Stories

### US-0.1: Profile-Aware Responses
> As a returning student, I should not be asked "which class?" when my profile already has class 10 AI set.

**Problem:** 14% of all bot responses are "please specify your class/subject" — even for students who already have this in their profile. The bot re-asks because profile context isn't consistently passed to the LLM.

**Root Cause:** `_build_system_prompt` in `agent_service.py` has an inconsistency — line 62 calls `PromptFactory` without `is_admin`, but line 120 passes it. More critically, user profile data (class, subject) isn't being injected into the system prompt reliably, causing the LLM to ask for information it should already have.

### US-0.2: Onboarding Flow
> As a new student using /start, I should be guided to set my class and subject before anything else.

**Problem:** 42% of registered users never set their class/subject. The current `/start` command sends a welcome message but doesn't enforce profile setup. Students jump straight to asking for notes, hit "please specify," and some never come back.

### US-0.3: Admin Flag
> As an admin, the is_admin flag should work correctly in system prompts.

**Problem:** The `is_admin` parameter is passed in one code path but not another, leading to inconsistent admin detection.

---

## Acceptance Criteria

### AC-1: Fix is_admin passthrough
- [ ] `_build_system_prompt` consistently passes `is_admin` to `PromptFactory` in all code paths
- [ ] Admin users see admin-specific instructions in bot behavior
- [ ] Non-admin users do not see admin capabilities

### AC-2: Onboarding flow after /start
- [ ] `/start` triggers an interactive onboarding sequence
- [ ] Student must select class (10, 11, 12) before proceeding
- [ ] Student must select subject (AI, CS, IT, IP) before proceeding
- [ ] Selections are saved to profile via `UserService`
- [ ] If a returning user runs `/start`, show current profile and offer to update
- [ ] Bot does not process study-related queries until profile is complete

### AC-3: Use profile defaults for notes
- [ ] When user says "notes" and profile has class + subject, use those defaults
- [ ] Only ask for clarification if profile is incomplete OR the request is ambiguous (e.g., "notes for a different subject")
- [ ] System prompt includes explicit instruction: "User's class is {class}, subject is {subject}. Use these as defaults."

### AC-4: Metric targets
- [ ] "Please specify" response rate drops from 14% to under 3%
- [ ] Profile completion rate rises from 58% to over 85% (for new users post-fix)

---

## Implementation Plan

### Step 1: Fix is_admin in agent_service.py

**File:** `telegram_bot/services/agent_service.py`

Audit all calls to `PromptFactory` and `_build_system_prompt`. Ensure `is_admin` is passed through consistently. The fix is straightforward: find the call site at line ~62 that omits `is_admin` and add it.

### Step 2: Inject profile context into system prompt

**File:** `telegram_bot/prompts/agent_system.md`

Add a `## Student Profile` section to the system prompt template:

```
## Student Profile
- Class: {class}
- Subject: {subject}
- Username: {username}

When the student asks for notes, resources, or explanations, use their class and subject as defaults.
Do NOT ask "which class?" or "which subject?" if this information is already provided above.
Only ask for clarification if the student explicitly requests a different class or subject.
```

**File:** `telegram_bot/services/agent_service.py`

Ensure the template variables are populated from user profile before building the prompt.

### Step 3: Build onboarding flow

**File:** `telegram_bot/handlers.py`

After `/start`:
1. Check if user profile has class + subject set
2. If not: send inline keyboard with class options (10, 11, 12)
3. On class selection: send inline keyboard with subject options (AI, CS, IT, IP)
4. On subject selection: save profile, confirm, and show welcome message with capabilities
5. If profile already complete: show current profile with "Update" button

### Step 4: Smart defaults for notes tool

**File:** `telegram_bot/prompts/agent_system.md`

Strengthen the instruction to use profile defaults. The LLM should infer class/subject from profile context without asking.

---

## Files to Modify

| File | Change |
|------|--------|
| `telegram_bot/services/agent_service.py` | Fix `is_admin` passthrough, inject profile into prompt |
| `telegram_bot/handlers.py` | Add onboarding flow after `/start` |
| `telegram_bot/prompts/agent_system.md` | Add student profile section, strengthen default instructions |

---

## Testing

1. **is_admin fix:** Send message as admin user → verify admin instructions appear in prompt (log it)
2. **Onboarding:** Fresh user → `/start` → verify class/subject selection flow → verify profile saved
3. **Returning user:** User with profile says "notes" → verify bot uses defaults, does not ask class/subject
4. **Incomplete profile:** User without class says "notes" → verify bot asks politely once, then remembers

---

## Rollback

No database changes, no new dependencies. Rollback = revert the commit.
