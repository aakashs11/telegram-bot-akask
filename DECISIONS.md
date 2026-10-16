# ASK AI - Architecture Decision Log

> Immutable record of all architecture decisions. Never modify an accepted entry. When a decision changes, create a new entry that supersedes the old one.
> 
> See also: `.cursor/plans/technology-decisions.md` for the full ADR documents.

---

## How to Use This Log

1. When making an architecture/technology decision during development, add a new entry
2. Use the next sequential number (ADR-NNN)
3. If changing a previous decision, set the old one's status to "Superseded by ADR-NNN"
4. Keep entries concise (3-5 lines max per section)

---

## Decision Log

### ADR-001: Primary LLM -- Smart Routing
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** GPT-4o for doubts/explanations, Gemini 2.5 Flash (free) for notes/links/greetings
**Rationale:** Quality where it matters, free where it doesn't

### ADR-002: Database -- Supabase PostgreSQL (Separate Project)
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Dedicated Supabase project for bot data (not shared with academy-platform)
**Rationale:** Isolation, free tier sufficient (500MB, 50K MAU)

### ADR-003: Embeddings -- gemini-embedding-001
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Google's gemini-embedding-001 for all embeddings (memory + content)
**Rationale:** FREE tier, 3072 dims (scalable to 768 via MRL)

### ADR-004: Memory -- Mem0 Self-hosted
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Mem0 with Supabase pgvector backend for persistent student memory
**Rationale:** Python-native, free, 50K+ stars, works with existing OpenAI key

### ADR-005: Document Parsing -- IBM Docling + PyMuPDF fallback
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Docling for structured docs (tables, formatted), PyMuPDF for simple text
**Rationale:** Docling 97.9% table accuracy vs PyMuPDF 80.6%. Docling runs locally, MIT license, 56K+ stars

### ADR-006: RAG -- Gemini File Search Tool
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Use Gemini's managed File Search for content RAG instead of custom pipeline
**Rationale:** Fully managed: auto-chunk, auto-embed, auto-index. Storage + query-time embeddings FREE. Reduces Phase 3 from 3 weeks to ~1 week

### ADR-007: Vector Store Split
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Two vector stores: Gemini File Search (content RAG) + Supabase pgvector (Mem0 memory)
**Rationale:** File Search handles content grounding natively. pgvector handles memory retrieval for Mem0

### ADR-008: Admin Dashboard -- Extend Academy Platform
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Extend existing academy-platform admin pages (React + Supabase)
**Rationale:** Admin pages already exist at /admin/*. Don't rebuild from scratch

### ADR-009: Multi-Platform -- Adapter Pattern
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Platform-agnostic ChatMessage/ChatResponse contracts with thin adapters
**Rationale:** Reuse brain across Telegram, Discord, website. Each adapter ~100 lines

### ADR-010: Answer Format -- Auto-Detection
**Date:** 2026-03-24 | **Status:** Accepted
**Decision:** Auto-detect answer format from student phrasing (explain -> detailed, define -> 1-mark, discuss -> 3-5 mark)
**Rationale:** Students shouldn't have to specify format. Bot infers from natural language

### ADR-011: PostgreSQL Access -- Provider-Neutral Async SQLAlchemy
**Date:** 2026-09-22 | **Status:** Accepted
**Decision:** Use SQLAlchemy async with asyncpg and Alembic behind `DATABASE_URL`, with temporary feature-flagged Sheets/PostgreSQL dual-write.
**Rationale:** Portable infrastructure and shared idempotency keys enable a measurable migration without coupling application services to a database vendor SDK.

### ADR-012: Interaction Backfill -- Stable Snapshot with Raw Timestamps
**Date:** 2026-09-22 | **Status:** Accepted
**Decision:** Backfill bounded rows from an immutable Sheet export using deterministic source references while storing both UTC-normalized and raw source timestamps.
**Rationale:** Stable row identity makes retries idempotent, and preserving source text allows timezone conversion and payload reconciliation to remain auditable.

### ADR-013: Student Profiles -- One Row per Telegram User
**Date:** 2026-10-03 | **Status:** Accepted
**Decision:** Store student profiles in a `students` table keyed by Telegram user id, with class and subject limited to the values the bot already accepts.
**Rationale:** The columns match the UserProfiles sheet, so existing profiles can be copied before UserService switches off Sheets.

### ADR-014: Content Catalog -- One Row per Drive File
**Date:** 2026-10-13 | **Status:** Accepted
**Decision:** Store the Index sheet in `content_items`, keyed by Drive file id, with level, subject, type, and topic kept as the folder text the sync wrote.
**Rationale:** The catalog points at files that stay in Drive, and folder names such as "Class 12" or "Computer Vision" are not the same closed list as a student profile.

### ADR-015: Drive Folders -- Path Lookup Beside the File Catalog
**Date:** 2026-10-13 | **Status:** Accepted
**Decision:** Store the Folders sheet in a `folders` table keyed by Drive folder id, with a unique path.
**Rationale:** Notes lookup asks for a path such as Class 10/AI/Notes and needs one URL, while the folder id stays stable if the path is edited.

### ADR-016: Sheet Data Switch -- Profiles and Catalog Behind One Flag
**Date:** 2026-10-13 | **Status:** Accepted
**Decision:** Read student profiles, the content catalog, and folder links from Postgres only when `BOT_DATA_STORE=postgres`; the default remains Google Sheets.
**Rationale:** Local testing can use the copied tables without changing production, which still has no database URL.

### ADR-017: Moderation Strikes -- One Row per User and Chat
**Date:** 2026-10-13 | **Status:** Accepted
**Decision:** Store the Warnings sheet in `warnings`, keyed by Telegram user id and chat id together, and read it through the same `BOT_DATA_STORE` flag.
**Rationale:** It is the last sheet the bot reads back during a conversation, and one student can hold a separate strike count in each group.

### ADR-018: Drive Sync -- Replace the Catalog Tables Behind the Same Flag
**Date:** 2026-10-13 | **Status:** Accepted
**Decision:** When `BOT_DATA_STORE=postgres`, a Drive sync replaces `content_items` and `folders` and leaves the Index and Folders sheets unchanged.
**Rationale:** The bot reads those tables, so a new PDF has to land there, while production stays on the sheet rewrite until the flag is set.

### ADR-019: Historical Logs Stay on the Sheet
**Date:** 2026-10-14 | **Status:** Accepted
**Decision:** Do not copy the old `Logs` sheet into `interaction_events`. New messages are dual-written for the cutover window, and the sheet remains the archive of older messages.
**Rationale:** The bot does not read those old rows to answer a student, and a few days of dual-write is enough to prove that new log rows match.

### ADR-020: Supabase Free with a Weekly Dump
**Date:** 2026-10-14 | **Status:** Accepted
**Decision:** Use the Supabase Free plan for the first production database, with a weekly `pg_dump` stored off the project, instead of requiring Pro before Postgres is the live store.
**Rationale:** The copied tables are a few megabytes, far under the 500 MB free database quota, and a tested dump is the backup Free does not provide.

---

## Changelog

| Date | ADR | Change | Impact |
|------|-----|--------|--------|
| 2026-03-24 | ADR-001 to ADR-010 | Initial architecture decisions from V0 planning session | Foundation for all development |
| 2026-10-03 | ADR-013 | Add `students` table matching the UserProfiles sheet | Profile migration can start without new account types |
| 2026-10-13 | ADR-014 | Add `content_items` keyed by Drive file id | Notes catalog can be copied without moving PDF bytes |
| 2026-10-13 | ADR-015 | Add `folders` keyed by Drive folder id with a unique path | Notes lookup can resolve a class/subject/type path to one URL |
| 2026-10-13 | ADR-016 | `BOT_DATA_STORE` selects Sheets or Postgres for profiles and the catalog | Production stays on Sheets until the flag is set |
| 2026-10-13 | ADR-017 | Add `warnings` keyed by user id and chat id | Group strikes can leave Sheets before the scripted cases |
| 2026-10-13 | ADR-018 | Postgres mode replaces the catalog tables from Drive | New files reach the tables the bot reads |
| 2026-10-14 | ADR-019 | Leave historical `Logs` on the sheet | Cutover does not depend on a backfill or a confirmed old timezone |
| 2026-10-14 | ADR-020 | Supabase Free plus a weekly `pg_dump` | Pro is not required for the first live database |
