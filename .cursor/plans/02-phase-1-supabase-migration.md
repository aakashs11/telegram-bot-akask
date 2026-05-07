# Phase 1: Supabase Migration

**Duration:** Week 1-2  
**Dependencies:** None (Phase 0 is nice-to-have first but not blocking)  
**Technology:** Supabase PostgreSQL, asyncpg, SQLAlchemy async, supabase-py  

---

## User Stories

### US-1.1: Real Database
> As a developer, I want all data in a real database so I don't hit Google Sheets rate limits.

**Problem:** Google Sheets API has a 60 requests/minute quota. During peak hours (after school, 3-5 PM), the bot hits rate limits and drops requests. Sheets also lacks indexing, transactions, and concurrent writes.

### US-1.2: Faster Responses
> As a student, I want the bot to respond faster (no Sheets API latency).

**Problem:** Every Sheets API call adds 200-800ms of latency. Profile lookups, logging, and content index queries all go through Sheets. A single interaction can make 3-4 Sheets calls.

### US-1.3: SQL Access
> As an admin, I want to query student data with SQL.

**Problem:** Analyzing the 14,470+ interaction logs requires exporting CSVs from Sheets and processing in Python. No way to run ad-hoc queries like "how many students asked about Neural Networks this week?"

---

## Acceptance Criteria

### AC-1: Supabase Setup
- [ ] New Supabase project created (separate from academy-platform)
- [ ] Connection pooling configured (PgBouncer)
- [ ] Row Level Security policies defined
- [ ] Service role key stored in Google Secret Manager

### AC-2: Schema Deployed
- [ ] All 5 tables created with proper constraints and indexes
- [ ] pgvector extension enabled (for Phase 2 embedding column)
- [ ] `content_index.embedding` column as `VECTOR(768)` ready for Phase 2

### AC-3: Services Migrated
- [ ] `UserService` reads/writes from Supabase instead of Sheets
- [ ] `gspread_logging` replaced with async Supabase inserts
- [ ] `DriveNoteRepository` uses `content_index` table
- [ ] `SyncService` writes to `content_index` and `folders` tables
- [ ] `WarningService` uses `bot_warnings` table

### AC-4: Data Migration
- [ ] Migration script imports 1,369 user profiles
- [ ] Migration script imports 14,470+ interaction logs
- [ ] Migration script imports 203 indexed content files
- [ ] Migration script imports folder mappings
- [ ] Data integrity verified: row counts match, spot-check 50 random records

### AC-5: Zero Downtime
- [ ] Feature flag `USE_SUPABASE` in settings.py
- [ ] Dual-write mode: write to both Sheets and Supabase during transition
- [ ] Read from Supabase when flag is on, Sheets when off
- [ ] Google Sheets kept as read-only backup for 2 weeks post-migration
- [ ] Rollback path: flip flag back to Sheets

---

## Database Schema

```sql
-- Enable pgvector for Phase 2
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- bot_users: Student profiles (migrated from Google Sheets)
-- ============================================================
CREATE TABLE bot_users (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT UNIQUE,
    discord_id    TEXT UNIQUE,
    website_user_id UUID UNIQUE,
    username      TEXT,
    current_class TEXT CHECK (current_class IN ('10', '11', '12')),
    preferred_subject TEXT CHECK (preferred_subject IN ('AI', 'CS', 'IT', 'IP')),
    is_admin      BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_active   TIMESTAMPTZ DEFAULT NOW(),
    class_updated_year INT DEFAULT EXTRACT(YEAR FROM NOW())
);

CREATE INDEX idx_bot_users_telegram ON bot_users(telegram_id);
CREATE INDEX idx_bot_users_last_active ON bot_users(last_active);

-- ============================================================
-- bot_interactions: Conversation logs (migrated from Sheets)
-- ============================================================
CREATE TABLE bot_interactions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT REFERENCES bot_users(id) ON DELETE SET NULL,
    platform      TEXT DEFAULT 'telegram' CHECK (platform IN ('telegram', 'discord', 'website')),
    user_message  TEXT NOT NULL,
    bot_response  TEXT,
    intent        TEXT,
    tokens_used   INT DEFAULT 0,
    model_used    TEXT,
    response_ms   INT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_interactions_user ON bot_interactions(user_id);
CREATE INDEX idx_interactions_created ON bot_interactions(created_at DESC);
CREATE INDEX idx_interactions_intent ON bot_interactions(intent);

-- ============================================================
-- content_index: Drive files + future RAG content
-- ============================================================
CREATE TABLE content_index (
    id            BIGSERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    link          TEXT,
    level         TEXT CHECK (level IN ('10', '11', '12')),
    subject       TEXT CHECK (subject IN ('AI', 'CS', 'IT', 'IP')),
    resource_type TEXT,
    topic         TEXT,
    drive_file_id TEXT UNIQUE,
    content_text  TEXT,
    embedding     VECTOR(768),
    synced_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_content_level_subject ON content_index(level, subject);
CREATE INDEX idx_content_type ON content_index(resource_type);
CREATE INDEX idx_content_drive ON content_index(drive_file_id);

-- ============================================================
-- folders: Drive folder mappings for sync
-- ============================================================
CREATE TABLE folders (
    id         BIGSERIAL PRIMARY KEY,
    path       TEXT NOT NULL UNIQUE,
    folder_id  TEXT NOT NULL,
    url        TEXT
);

-- ============================================================
-- bot_warnings: Moderation warnings
-- ============================================================
CREATE TABLE bot_warnings (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES bot_users(id) ON DELETE CASCADE,
    chat_id    BIGINT,
    reason     TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_warnings_user ON bot_warnings(user_id);
CREATE INDEX idx_warnings_chat ON bot_warnings(chat_id);
```

---

## Implementation Plan

### Week 1: Setup + Schema + Migration Script

#### Day 1-2: Supabase Project Setup
1. Create Supabase project (region: Mumbai for India latency)
2. Run schema SQL above
3. Enable pgvector extension
4. Configure connection pooling
5. Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to Secret Manager
6. Add `SUPABASE_DB_URL` (direct connection for SQLAlchemy)

#### Day 3-4: Database Infrastructure
**New file:** `telegram_bot/infrastructure/database.py`
- Async SQLAlchemy engine with connection pooling
- Session factory with context manager
- Health check function
- Graceful shutdown

#### Day 5: Migration Script
**New file:** `scripts/migrate_sheets_to_supabase.py`
- Read all data from Google Sheets
- Transform to match new schema (column name mapping, type conversion)
- Batch insert into Supabase (500 rows at a time)
- Verify row counts and spot-check data
- Generate migration report

### Week 2: Service Migration + Dual-Write + Cutover

#### Day 6-7: Migrate UserService
**File:** `telegram_bot/services/user_service.py`
- Replace gspread calls with SQLAlchemy queries
- Keep same public API (get_user, update_user, etc.)
- Add feature flag check: `if settings.USE_SUPABASE`

#### Day 8: Migrate Logging
**File:** `utils/gspread_logging.py`
- Replace with async Supabase inserts to `bot_interactions`
- Fire-and-forget pattern (don't block response on logging)
- Batch writes for high-throughput periods

#### Day 9: Migrate Content + Sync
**Files:** `telegram_bot/infrastructure/drive_note_repository.py`, `telegram_bot/services/sync_service.py`
- Content queries against `content_index` table
- Sync writes to `content_index` and `folders`

#### Day 10: Migrate Warnings + Testing + Cutover
**File:** `telegram_bot/services/moderation/warning_service.py`
- Warning CRUD against `bot_warnings` table
- End-to-end testing of all flows
- Enable `USE_SUPABASE=true` in production
- Monitor for 24 hours before disabling Sheets writes

---

## Files to Modify

| File | Change |
|------|--------|
| `config/settings.py` | Add Supabase config, `USE_SUPABASE` flag |
| `telegram_bot/services/user_service.py` | Replace Sheets with Supabase queries |
| `utils/gspread_logging.py` | Replace Sheets logging with async DB inserts |
| `telegram_bot/infrastructure/drive_note_repository.py` | Query content_index table |
| `telegram_bot/services/sync_service.py` | Write to content_index and folders tables |
| `telegram_bot/services/moderation/warning_service.py` | Use bot_warnings table |
| `requirements.txt` | Add asyncpg, sqlalchemy[asyncio], supabase |

## New Files

| File | Purpose |
|------|---------|
| `telegram_bot/infrastructure/database.py` | Async SQLAlchemy engine, session factory, pool config |
| `scripts/migrate_sheets_to_supabase.py` | One-time data migration from Sheets to Supabase |

---

## Configuration

```python
# config/settings.py additions
SUPABASE_URL: str           # from Secret Manager
SUPABASE_SERVICE_KEY: str   # from Secret Manager
SUPABASE_DB_URL: str        # direct postgres connection for SQLAlchemy
USE_SUPABASE: bool = False  # feature flag for gradual rollout
```

---

## Rollback Plan

1. Set `USE_SUPABASE=false` in Cloud Run environment
2. Redeploy — bot immediately reads/writes from Google Sheets again
3. No data loss: dual-write ensures both stores have the same data during transition
4. Sheets remain read-only backup for 2 weeks post-cutover

---

## Testing

1. **Unit tests:** Each migrated service tested against a test Supabase project
2. **Migration verification:** Row count comparison, random record spot-checks
3. **Load test:** Simulate 50 concurrent users hitting profile + notes + logging
4. **Latency test:** Compare p50/p95 response times before and after migration
5. **Failover test:** Flip `USE_SUPABASE` off mid-session → verify Sheets fallback works
