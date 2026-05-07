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

---

## Changelog

| Date | ADR | Change | Impact |
|------|-----|--------|--------|
| 2026-03-24 | ADR-001 to ADR-010 | Initial architecture decisions from V0 planning session | Foundation for all development |
