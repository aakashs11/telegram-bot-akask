# Phase 5: Website Unification

**Timeline:** Week 9-11
**Status:** Not Started
**Dependencies:** Phase 1 (Supabase), Phase 2 (Memory), Phase 3 (Content RAG)

---

## User Stories

1. **As a student**, my Telegram bot conversations should be visible on the website so I can review past explanations and answers on a bigger screen.
2. **As a student**, I should see my learning progress visualized on the website so I can understand my strengths, weaknesses, and study patterns.
3. **As an admin**, I should upload new content from the website dashboard so I don't need direct Google Drive or database access.
4. **As an admin**, I should see analytics about student usage so I can understand what students need and improve the platform.

---

## Acceptance Criteria

### Account Linking
- `bot_users.website_user_id` column links Telegram user ID to Supabase Auth user UUID
- `/link` command generates a one-time 6-character alphanumeric code (expires in 10 minutes)
- Student enters code on website to link their Telegram account
- Once linked, website and bot share the same user identity
- `/unlink` command removes the association
- One Telegram account maps to exactly one website account (1:1)

### Shared Memory
- Academy platform AI Tutor widget reads from the same Mem0 memory store
- Conversations on the website add to the same memory as Telegram conversations
- Memory context is platform-tagged (`source: "telegram"` / `source: "website"`) for audit

### Admin Dashboard Extensions
- **Bot Analytics page:** active users, messages/day, top queries, content gaps, response times
- **Content Ingestion UI:** drag-and-drop PDF upload, preview parsed chunks, approve/reject before indexing
- **Memory Browser:** search and view any student's memory entries, with ability to delete incorrect memories
- **Prompt Editor:** edit system prompts (agent_system.md, group prompts) from the UI with version history

### Student Learning Dashboard
- **Topics Studied:** list of all topics the student has interacted with, sorted by recency
- **Strengths/Weaknesses Radar:** radar chart showing proficiency across subjects/units
- **Activity Timeline:** chronological view of interactions (questions asked, notes accessed, quizzes taken)
- **Conversation History:** searchable archive of all bot conversations

---

## Technology

| Component | Technology |
|---|---|
| Auth | Supabase Auth (email + Google OAuth) |
| Frontend | React 19 + Vite (existing academy platform) |
| Backend | Supabase Edge Functions + existing FastAPI |
| State Sync | Supabase Realtime for live dashboard updates |
| Charts | Recharts or Chart.js for visualizations |

---

## Architecture

### Account Linking Flow

```
Student on Telegram          Website
       |                        |
  /link command                 |
       |                        |
  Bot generates code            |
  (stored in Supabase           |
   with telegram_id,            |
   expires_at)                  |
       |                        |
  Student enters code --------> POST /api/link-account
       |                        |
       |                  Validates code,
       |                  updates bot_users.website_user_id
       |                        |
       |                  Returns success
       |                        |
  Bot confirms linking          |
```

### Shared Data Model

```sql
-- Extends existing bot_users table
ALTER TABLE bot_users ADD COLUMN website_user_id UUID REFERENCES auth.users(id);
ALTER TABLE bot_users ADD COLUMN linked_at TIMESTAMPTZ;

-- Account linking codes
CREATE TABLE account_link_codes (
    code VARCHAR(6) PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES bot_users(telegram_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE
);

-- Conversation history (platform-agnostic)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES bot_users(telegram_id),
    platform VARCHAR(20) NOT NULL, -- 'telegram', 'website', 'discord'
    role VARCHAR(10) NOT NULL,     -- 'user', 'assistant'
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin analytics materialized views
CREATE MATERIALIZED VIEW daily_usage_stats AS
SELECT
    DATE(created_at) as date,
    COUNT(DISTINCT user_id) as active_users,
    COUNT(*) as total_messages,
    platform
FROM conversations
GROUP BY DATE(created_at), platform;
```

---

## Academy Platform Files to Modify

### Existing Files

| File | Change |
|---|---|
| `ui/src/hooks/useAITutor.js` | Connect to shared Mem0 memory store via API; send platform tag with each message |
| `ui/src/contexts/ProgressContext.jsx` | Replace localStorage with Supabase queries; sync progress from bot interactions |
| `ui/src/pages/admin/*` | Extend with bot-specific admin pages (analytics, content, memory, prompts) |
| `ui/src/App.jsx` | Add routes for new dashboard and admin pages |
| `ui/src/components/Sidebar.jsx` | Add navigation items for new pages |

### New Files to Create

| File | Purpose |
|---|---|
| `ui/src/pages/dashboard/LearningDashboard.jsx` | Student's progress overview page |
| `ui/src/pages/dashboard/ConversationHistory.jsx` | Searchable chat history |
| `ui/src/pages/admin/BotAnalytics.jsx` | Usage stats, charts, top queries |
| `ui/src/pages/admin/ContentIngestion.jsx` | PDF upload and chunk preview UI |
| `ui/src/pages/admin/MemoryBrowser.jsx` | Search/view/delete student memories |
| `ui/src/pages/admin/PromptEditor.jsx` | Edit prompts with version history |
| `ui/src/pages/LinkAccount.jsx` | Code entry page for account linking |
| `ui/src/hooks/useBotAnalytics.js` | Data fetching hook for analytics |
| `ui/src/hooks/useConversations.js` | Data fetching hook for chat history |

### Bot-Side Changes

| File | Change |
|---|---|
| `telegram_bot/handlers.py` | Add `/link` and `/unlink` command handlers |
| `telegram_bot/services/user_service.py` | Add `generate_link_code()`, `link_account()`, `unlink_account()` |
| `telegram_bot/services/agent_service.py` | Store conversations to `conversations` table |
| FastAPI endpoints | Add `/api/link-account`, `/api/conversations`, `/api/analytics` |

---

## Implementation Tasks

### Week 9: Account Linking + Conversation Storage
1. Create `account_link_codes` and `conversations` tables in Supabase
2. Add `website_user_id` column to `bot_users`
3. Implement `/link` command handler (generate code, store, send to user)
4. Implement `/unlink` command handler
5. Build `LinkAccount.jsx` page on website
6. Build API endpoint to validate code and link accounts
7. Start storing all bot conversations to `conversations` table
8. Test end-to-end linking flow

### Week 10: Student Dashboard + Shared Memory
9. Connect `useAITutor.js` to shared Mem0 memory store
10. Migrate `ProgressContext.jsx` from localStorage to Supabase
11. Build `LearningDashboard.jsx` with topic list and activity timeline
12. Build strengths/weaknesses radar chart component
13. Build `ConversationHistory.jsx` with search and filters
14. Test cross-platform memory: ask on Telegram, verify context on website

### Week 11: Admin Dashboard
15. Build `BotAnalytics.jsx` with usage charts (active users, messages/day, top queries)
16. Create materialized views for analytics queries
17. Build `ContentIngestion.jsx` with drag-and-drop upload, chunk preview, approve/reject
18. Build `MemoryBrowser.jsx` with student search, memory list, delete capability
19. Build `PromptEditor.jsx` with markdown editor, save, version history
20. End-to-end testing of all admin flows
21. Deploy and monitor

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Students don't bother linking accounts | Low website adoption | Make linking optional; bot works fully standalone |
| Memory store grows too large for dashboard queries | Slow page loads | Pagination, caching, materialized views |
| Admin accidentally deletes important memories | Data loss | Soft delete with 30-day recovery window |
| Prompt editor changes break the bot | Service disruption | Prompt version history with instant rollback |
| Cross-platform identity leaks | Privacy concern | RLS policies ensure students only see their own data |

---

## Success Metrics

- 30%+ of active bot users link their website accounts within 4 weeks of launch
- Admin content upload reduces time-to-publish from hours to minutes
- Dashboard page load < 2 seconds for 95th percentile
- Zero cross-user data leaks (verified by RLS audit)
