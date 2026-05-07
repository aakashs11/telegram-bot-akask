# Phase 3: Content Intelligence / RAG

**Timeline:** Week 5–7  
**Dependencies:** Phase 1 (Supabase + pgvector), Phase 2 (persistent memory for context)  
**Goal:** Transform ASK AI from a file-server into a knowledge engine that answers doubts from actual course content.

---

## User Stories

1. **As a student**, when I ask "explain backpropagation", I should get an actual explanation from my course content — not a Drive folder link.
2. **As a student**, I should be able to ask questions about what Aakash Sir explained in a YouTube video.
3. **As an admin**, I should be able to add new PDFs to the knowledge base without code changes.
4. **As a student**, answers should cite which chapter/PDF/video the information comes from.

---

## Acceptance Criteria

- [ ] **Content ingestion pipeline:** Download PDFs from Drive → parse with Gemini 2.5 Flash (FREE, multimodal) → chunk → embed with gemini-embedding-001 (FREE) → store in `content_index.embedding` (pgvector)
- [ ] **YouTube transcript ingestion:** youtube-transcript-api → chunk → embed → store
- [ ] **New `AskContentTool`** registered with AgentService for semantic search over content
- [ ] **Smart LLM routing:** If query is conceptual/doubt → GPT-4o; if query is "give me notes" → Gemini Flash (free)
- [ ] **Source citations in every answer:** e.g. `Source: Unit 3 NLP Notes, Class 10 AI` or `Source: YouTube — NLP One Shot, timestamp 14:32`
- [ ] **Admin ingestion trigger:** `/ingest` command or dashboard button
- [ ] **Custom notes:** Admin can upload any PDF via admin interface for indexing

---

## Technology

| Component | Technology | Cost |
|---|---|---|
| PDF parsing | Gemini 2.5 Flash (multimodal, up to 1000 pages) | FREE |
| Embeddings | gemini-embedding-001 (3072 dims, MRL scalable to 768) | FREE |
| Vector store | Supabase pgvector | Included in Supabase plan |
| YouTube transcripts | youtube-transcript-api | FREE |
| PDF fallback extraction | pymupdf (already in academy-platform content_agent) | FREE |
| Quality LLM | GPT-4o (for doubt-solving synthesis) | Paid |
| Cheap LLM | Gemini 2.5 Flash (for retrieval-only queries) | FREE |

---

## Pipeline Architecture

```
Content Sources                    Processing                     Storage              Query Time
┌──────────────┐
│ Google Drive  │──┐
│ (200+ PDFs)  │  │
└──────────────┘  │   ┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
                  ├──▶│ Gemini 2.5 Flash│───▶│ Chunking     │───▶│ gemini-     │
┌──────────────┐  │   │ (parse/extract) │    │ 500 tokens   │    │ embedding-  │
│ YouTube      │──┤   └─────────────────┘    │ 100 overlap  │    │ 001 (embed) │
│ Transcripts  │  │                          └──────────────┘    └──────┬──────┘
└──────────────┘  │                                                     │
                  │                                                     ▼
┌──────────────┐  │                                              ┌─────────────┐
│ Custom PDFs  │──┘                                              │ pgvector    │
│ (admin)      │                                                 │ (store)     │
└──────────────┘                                                 └──────┬──────┘
                                                                        │
                              ┌─────────────────────────────────────────┘
                              ▼
                    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
                    │ Semantic Search  │───▶│ LLM Synthesizes │───▶│ Answer with  │
                    │ (query time)     │    │ Answer          │    │ Citations    │
                    └──────────────────┘    └─────────────────┘    └──────────────┘
```

### Ingestion Flow (Detail)

1. **PDF Ingestion:**
   - Download PDF from Google Drive via Drive API (existing sync_service.py pattern)
   - Send to Gemini 2.5 Flash with prompt: "Extract all text content, preserve headings, tables, and diagrams as descriptions"
   - Chunk extracted text: 500 tokens per chunk, 100 token overlap
   - Generate embedding per chunk via gemini-embedding-001
   - Store in `content_chunks` table with metadata (class, subject, chapter, source_pdf, page_range)

2. **YouTube Transcript Ingestion:**
   - Fetch transcript via youtube-transcript-api for each video on the channel
   - Chunk transcript with timestamps preserved: 500 tokens per chunk, 100 token overlap
   - Each chunk retains start/end timestamps for citation
   - Generate embedding per chunk via gemini-embedding-001
   - Store in `content_chunks` table with metadata (video_id, video_title, class, subject, timestamp_start, timestamp_end)

3. **Query-Time Retrieval:**
   - Embed the student's question via gemini-embedding-001
   - Search pgvector for top-K (K=5) most similar chunks
   - Pass retrieved chunks + student question to LLM for synthesis
   - LLM generates answer with inline citations

---

## Smart Routing Logic

```
Student Query
     │
     ▼
┌─────────────────────────────────────────────┐
│ Classify intent from keywords + context     │
│                                             │
│ CONCEPTUAL DOUBT keywords:                  │
│   "explain", "what is", "how does",         │
│   "difference between", "define", "why",    │
│   "compare", "discuss"                      │
│   → Route to GPT-4o (quality matters)       │
│                                             │
│ RETRIEVAL keywords:                         │
│   "notes", "pdf", "material", "download",   │
│   "link", "book", "chapter", "send"         │
│   → Route to Gemini Flash (just retrieval)  │
│                                             │
│ DEFAULT:                                    │
│   → Gemini Flash (save money on simple)     │
└─────────────────────────────────────────────┘
```

Routing is implemented in `agent_service.py` before the LLM call. The system prompt and tool availability remain the same regardless of which model handles the query — only the model endpoint changes.

---

## Database Schema (extends Phase 1 Supabase)

```sql
CREATE TABLE content_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL CHECK (source_type IN ('pdf', 'youtube', 'custom')),
    source_id TEXT NOT NULL,          -- drive_file_id or video_id
    source_title TEXT NOT NULL,       -- PDF name or video title
    class TEXT,                       -- '10', '11', '12'
    subject TEXT,                     -- 'AI', 'CS', 'IT', 'IP'
    chapter TEXT,                     -- chapter name if available
    chunk_index INTEGER NOT NULL,     -- order within source
    chunk_text TEXT NOT NULL,
    embedding VECTOR(768),            -- gemini-embedding-001 at MRL 768
    metadata JSONB DEFAULT '{}',      -- page_range, timestamp_start/end, etc.
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_content_chunks_embedding ON content_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_content_chunks_class_subject ON content_chunks (class, subject);

CREATE TABLE ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_title TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

---

## Files to Create

| File | Purpose |
|---|---|
| `telegram_bot/tools/ask_content_tool.py` | New tool: semantic search over content_chunks, returns synthesized answer with citations |
| `telegram_bot/services/ingestion_service.py` | Core ingestion logic: parse → chunk → embed → store. Handles PDFs and YouTube. |
| `telegram_bot/services/content_service.py` | Query-time retrieval: embed query → pgvector search → format context for LLM |
| `scripts/ingest_drive_content.py` | One-off script to bulk-ingest all 200+ existing Drive PDFs |
| `scripts/ingest_youtube_transcripts.py` | One-off script to bulk-ingest YouTube channel transcripts |

## Files to Modify

| File | Change |
|---|---|
| `telegram_bot/services/agent_service.py` | Add smart routing logic (keyword-based model selection), register AskContentTool |
| `telegram_bot/application.py` | Register AskContentTool in tool list |
| `config/settings.py` | Add `GEMINI_API_KEY`, embedding model config, chunk size params |
| `config/model_config.py` | Add Gemini Flash model config alongside GPT-4o |
| `requirements.txt` | Add `google-generativeai`, `youtube-transcript-api`, `pymupdf` |
| `telegram_bot/handlers.py` | Wire `/ingest` admin command |

---

## Implementation Tasks

### Week 5: Ingestion Pipeline

1. **Set up Gemini SDK and config**
   - Add `GEMINI_API_KEY` to settings and Secret Manager
   - Configure gemini-embedding-001 (768 dims via MRL) and Gemini 2.5 Flash
   - Run `content_chunks` and `ingestion_log` migrations on Supabase

2. **Build `ingestion_service.py`**
   - `ingest_pdf(drive_file_id)`: download → Gemini Flash parse → chunk → embed → store
   - `ingest_youtube(video_id)`: fetch transcript → chunk with timestamps → embed → store
   - `ingest_custom(file_bytes, metadata)`: admin-uploaded PDF → same pipeline
   - Chunking util: 500 tokens, 100 overlap, preserve paragraph boundaries
   - Idempotency: skip if source_id already in ingestion_log with status=completed

3. **Build bulk ingestion scripts**
   - `scripts/ingest_drive_content.py`: iterate all Drive PDFs from existing sync, call ingest_pdf for each
   - `scripts/ingest_youtube_transcripts.py`: fetch channel video list, call ingest_youtube for each
   - Progress tracking, resume on failure, logging

### Week 6: Query Pipeline + Smart Routing

4. **Build `content_service.py`**
   - `search_content(query, class_filter, subject_filter, top_k=5)`: embed query → pgvector cosine similarity → return chunks with metadata
   - Pre-filter by class/subject when user profile is known (from Phase 2 memory)
   - Format retrieved chunks into LLM context with source attribution

5. **Build `ask_content_tool.py`**
   - Extends `BaseTool` pattern from existing tools
   - Parameters: `query` (required), `class` (optional), `subject` (optional)
   - Calls `content_service.search_content()`, formats context, returns for LLM synthesis
   - LLM prompt instructs: "Answer using ONLY the provided context. Cite sources inline."

6. **Implement smart routing in `agent_service.py`**
   - Classify query intent from keywords + conversation history
   - Route conceptual doubts to GPT-4o, retrieval queries to Gemini Flash
   - Both models share the same system prompt and tool definitions
   - Fallback: if classification uncertain, use Gemini Flash (cheaper default)

### Week 7: Citations, Admin, Polish

7. **Citation formatting**
   - PDF sources: `📖 Source: {pdf_title}, Chapter {chapter}, Page {page_range}`
   - YouTube sources: `🎥 Source: {video_title}, Timestamp {mm:ss}` (with link)
   - Multiple sources: list all cited sources at end of answer

8. **Admin ingestion trigger**
   - `/ingest` command (admin-only): triggers re-scan of Drive + YouTube
   - `/ingest <drive_url>`: ingest a specific PDF
   - `/ingest <youtube_url>`: ingest a specific video
   - Status feedback: "Ingesting 3 new PDFs... Done. 47 chunks created."

9. **Testing and quality validation**
   - Test with real student queries from interaction logs (top 50 most common)
   - Validate citation accuracy: does the cited source actually contain the answer?
   - Measure latency: target < 5 seconds for RAG answers
   - Compare answer quality: RAG answer vs current "here's a folder link" response

---

## Cost Analysis

| Component | Volume | Cost |
|---|---|---|
| Gemini 2.5 Flash (parsing 200 PDFs) | ~2000 pages | FREE |
| gemini-embedding-001 (initial index) | ~10K chunks | FREE |
| gemini-embedding-001 (per query) | ~500/day | FREE |
| GPT-4o (doubt solving) | ~150/day (30% of 500) | ~$2-3/day |
| Gemini Flash (retrieval queries) | ~350/day (70% of 500) | FREE |
| pgvector storage | ~10K vectors × 768 dims | Included in Supabase |

**Net savings from smart routing:** ~60% reduction in OpenAI costs by routing simple queries to free Gemini Flash.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Gemini Flash parsing quality on scanned PDFs | Incomplete text extraction | Fallback to pymupdf for text-heavy PDFs; Gemini Flash for image-heavy |
| Hallucination in RAG answers | Wrong information to students | Strict prompt: "Use ONLY provided context. Say 'I don't have this in my notes' if unsure" |
| youtube-transcript-api rate limits | Ingestion failure | Batch with delays, cache transcripts, manual fallback |
| Embedding quality at 768 dims (MRL) | Poor retrieval | Test at 768 vs 3072; upgrade if recall drops significantly |
| Cold start latency (first query) | Slow response | Pre-warm embeddings model; cache frequent query embeddings |

---

## Success Metrics

- **Content coverage:** >80% of "explain X" queries return a RAG answer (vs 0% today)
- **Citation accuracy:** >90% of cited sources actually contain the referenced information
- **Student satisfaction:** Reduce "can't find content" responses from 14% to <5%
- **Cost efficiency:** Average cost per query drops 60% via smart routing
- **Latency:** RAG answers in <5 seconds (P95)
