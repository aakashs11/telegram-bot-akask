# ASK AI - Technology Decisions

Architecture Decision Records (ADRs) for the ASK AI educational platform.
Each decision documents context, alternatives, rationale, and consequences.

---

## Decision: Primary LLM — Smart Routing (GPT-4o + Gemini Flash)

**Status:** Accepted

**Context:** The bot handles a wide range of requests — from conceptual doubt-solving (requiring high-quality reasoning) to simple notes retrieval and greetings (where quality tolerance is high). Using GPT-4o for everything costs $10-15/month and is wasteful for trivial requests. Gemini 2.5 Flash offers a generous free tier.

**Decision:** Route requests to two LLMs based on intent:
- **GPT-4o** for doubts, explanations, conceptual questions, board-exam answers, and anything requiring nuanced reasoning.
- **Gemini 2.5 Flash** (FREE: 10 RPM, 250K TPM, 250 RPD) for notes requests, link retrieval, greetings, and simple lookups.
- Routing is performed via keyword detection in the user message before the LLM call.

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| GPT-4o only | Simplest, highest quality | $10-15/month, overkill for 28% of messages that are just "send me notes" |
| Gemini only | Free | Lower quality for detailed explanations, less reliable function-calling |
| GPT-4o-mini | Cheaper than GPT-4o | Still costs money, quality gap vs GPT-4o for CBSE explanations |
| Claude 3.5 Sonnet | Strong reasoning | Higher cost, no free tier, different API patterns |

**Rationale:** 28% of all messages are notes/PDF requests. Another ~15% are greetings or simple queries. Routing these to Gemini Flash saves ~40-50% of LLM costs while keeping GPT-4o quality for the requests that matter (doubt-solving, exam prep). The routing logic is simple keyword matching — low complexity, high savings.

**Consequences:**
- Two LLM clients to maintain (OpenAI + Google GenAI SDKs)
- Routing logic must be tested to avoid misclassification (e.g., "explain these notes" should go to GPT-4o)
- Fallback needed: if Gemini rate-limits, fall back to GPT-4o-mini
- Prompt templates may differ slightly between models

---

## Decision: Database — Supabase PostgreSQL (Separate Project)

**Status:** Accepted

**Context:** The bot currently stores everything in Google Sheets (profiles, logs, notes index, warnings). This is fragile, slow, and doesn't support vector search. The academy-platform (learnwithaakash.in) already uses Supabase. The question is whether to share that project or create a separate one.

**Decision:** Create a **separate Supabase project** dedicated to the bot. Use PostgreSQL with the pgvector extension for vector search capabilities.

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| Shared Supabase (same as academy-platform) | Single source of truth, shared user tables | Coupling risk — bot changes can break website, RLS complexity, shared rate limits |
| SQLite | Simplest, zero infrastructure | No vector search, no shared access from multiple services, no realtime |
| Firebase Firestore | Google ecosystem, vector search available | Different query patterns, no SQL, harder to join data |
| PlanetScale / Neon | Managed MySQL/PostgreSQL | No built-in vector search, additional cost |

**Rationale:** Separate projects avoid coupling risk — the bot can evolve independently. Supabase free tier gives 500MB storage and unlimited API requests, which is sufficient. pgvector is built in, avoiding a separate vector DB service. If unification is needed later (Phase 5), cross-database queries can be handled at the application layer or projects can be merged.

**Consequences:**
- Two Supabase projects to manage (bot + academy-platform)
- User data may need syncing between projects in Phase 5
- Migration scripts needed to move Google Sheets data to PostgreSQL
- Row-Level Security (RLS) policies must be configured for student data

---

## Decision: Embeddings — gemini-embedding-001 (Free)

**Status:** Accepted

**Context:** Content RAG (Phase 3) and memory (Phase 2) both require text embeddings. The bot processes CBSE educational content — textbook chapters, notes PDFs, and student queries. Embedding quality must be good enough for educational content retrieval.

**Decision:** Use **gemini-embedding-001** for all embedding needs.
- Free tier: 1,500 RPD, 1M tokens/min
- Output: 3072 dimensions (supports Matryoshka Representation Learning — scalable down to 768 for storage optimization)
- Used for both content indexing and memory embeddings (via Mem0)

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| OpenAI text-embedding-3-small | Good quality, 1536 dims | $0.02/1M tokens — adds up with 200+ PDFs |
| OpenAI text-embedding-3-large | Best quality, 3072 dims | $0.13/1M tokens — expensive for bootstrapping |
| Local models (all-MiniLM-L6-v2) | Free, fast, offline | Lower quality, complex deployment on Cloud Run |
| Cohere embed-v3 | Multilingual, free trial | Limited free tier, another vendor dependency |

**Rationale:** Free is the deciding factor at current scale. gemini-embedding-001 benchmarks competitively with OpenAI's offerings for English text. MRL support means we can start with 768 dimensions for storage efficiency and scale to 3072 if retrieval quality needs improvement. The embedding model is already part of the Google AI SDK used for Gemini Flash.

**Consequences:**
- Locked into Google's embedding space (switching later requires re-embedding all content)
- 768-dim MRL vectors use ~3KB each — manageable for thousands of chunks
- Must monitor free tier limits during bulk indexing (200+ PDFs)
- Embedding dimension choice (768 vs 3072) affects both storage and retrieval quality

---

## Decision: Vector Store — Supabase pgvector (Built into PostgreSQL)

**Status:** Accepted

**Context:** Vector search is needed for content RAG (find relevant textbook chunks) and memory retrieval (find relevant student context). The vector store must integrate with the existing database choice.

**Decision:** Use **Supabase pgvector** — the vector search extension built into PostgreSQL. Vectors are stored alongside relational data in the same database.

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| ChromaDB | Simple API, local file storage | Separate service to deploy, no shared queries with relational data |
| Pinecone | Managed, scalable, fast | Paid ($70/mo for starter), another vendor |
| Weaviate | Feature-rich, hybrid search | Complex setup, overkill for current scale |
| Firebase Firestore vector search | Google ecosystem | Would require switching database decision |
| FAISS | Fast, Facebook-backed | In-memory only, no persistence without custom code |

**Rationale:** pgvector eliminates the need for a separate vector database service. Content chunks can be stored with their metadata (class, subject, chapter, source PDF) in the same table, enabling hybrid queries like "find relevant chunks for Class 12 CS Unit 2" that combine vector similarity with SQL filters. Supabase provides helper functions for vector operations.

**Consequences:**
- Vector search performance is good for thousands of vectors, may need optimization at millions
- IVFFlat or HNSW indexes needed for performance as content grows
- All data in one place — simpler backup, simpler deployment
- Cannot easily switch to a specialized vector DB without migration

---

## Decision: Memory — Mem0 (Self-hosted with pgvector)

**Status:** Accepted

**Context:** 14% of bot responses are "please specify your class/subject" — the bot has no memory. 42% of registered users never set their class/subject. Students shouldn't have to repeat themselves. Memory should persist across sessions and be queryable.

**Decision:** Use **Mem0** (self-hosted) with Supabase pgvector as the storage backend.
- Python-native: `pip install mem0ai`
- 50K+ GitHub stars, active development
- Memory embeddings via gemini-embedding-001 (FREE)
- Memory extraction via GPT-4o-mini (cheap — ~$0.15/1M input tokens)
- Stores memories as semantic facts ("student is in Class 12, studying CS")

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| Supermemory / OpenClaw | Open-source, multi-platform | Requires Pro plan for full features, TypeScript (not Python), replaces bot architecture |
| Custom memory build | Full control | High complexity — entity extraction, deduplication, decay logic |
| No memory (status quo) | No work required | 14% of responses are avoidable clarification requests, poor UX |
| LangChain memory | Integrates with LangChain | Would require migrating from current OpenAI Responses API architecture |
| Simple key-value store | Easy to implement | No semantic search, no automatic extraction |

**Rationale:** Mem0 handles the hard parts — extracting facts from conversations, deduplicating memories, and retrieving relevant context. Self-hosting with pgvector avoids Mem0's cloud pricing and keeps data in our Supabase instance. GPT-4o-mini for extraction is cheap (~$0.001 per conversation turn). The Python SDK integrates cleanly with the existing FastAPI codebase.

**Consequences:**
- Mem0 is a dependency — must pin version and monitor for breaking changes
- Memory extraction adds latency (~200-500ms per message for GPT-4o-mini call)
- Privacy consideration: student memories stored in database, need data retention policy
- Memory quality depends on GPT-4o-mini's extraction — may need prompt tuning

---

## Decision: Document Parsing — Gemini 2.5 Flash (Free, Multimodal)

**Status:** Accepted

**Context:** The bot has 200+ PDFs on Google Drive covering CBSE curriculum. These need to be parsed into searchable chunks for RAG. PDFs contain text, tables, diagrams, flowcharts, and formatted layouts. Traditional text extraction misses visual content.

**Decision:** Use **Gemini 2.5 Flash** for document parsing via its multimodal capabilities.
- FREE tier: 250 RPD, 250K TPM
- Handles PDFs up to 1000 pages with native vision
- Understands tables, diagrams, charts, and complex layouts
- Already proven in the academy-platform's content_agent

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| PyPDF2 / pdfplumber | Free, fast, local | Text-only — misses tables, diagrams, charts entirely |
| Adobe PDF Services | High accuracy | Paid ($0.05/page), 500 free pages/month |
| AWS Textract | OCR + table extraction | Paid, AWS dependency, no semantic understanding |
| Unstructured.io | Open-source, multiple formats | Complex setup, inconsistent on formatted educational PDFs |
| LlamaParse | Good for complex PDFs | Paid beyond free tier, another dependency |

**Rationale:** Gemini Flash's multimodal capability means it can "see" the PDF pages rather than just extracting text. This is critical for CBSE content where diagrams (flowcharts in CS, network topologies in AI) and tables (comparison tables, mark distributions) carry significant information. The free tier handles the initial bulk parsing of 200+ PDFs, and the model is already integrated via the Google AI SDK.

**Consequences:**
- Parsing quality depends on Gemini's vision capabilities — may need manual review for complex diagrams
- Rate limits (250 RPD) mean bulk parsing must be batched over multiple days or use paid tier
- Parsed content needs chunking strategy (by section, by page, by semantic boundary)
- Must cache parsed results — re-parsing on every query would be wasteful and slow

---

## Decision: Admin Dashboard — Extend Academy Platform

**Status:** Accepted

**Context:** The bot needs admin features — viewing logs, managing content, monitoring usage, editing prompts. The academy-platform (learnwithaakash.in) already has an admin section built with React 19 + Vite + Supabase.

**Decision:** Extend the existing academy-platform admin dashboard rather than building a separate admin interface.

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| Separate FastAPI + HTMX dashboard | Python-native, simple | Another app to deploy, different stack from academy-platform |
| Telegram Mini App | Native to Telegram | Limited UI, complex development, poor for data-heavy views |
| Supabase Studio | Zero code | Very limited customization, no custom visualizations |
| Retool / Appsmith | Low-code, fast to build | Paid beyond free tier, vendor lock-in |

**Rationale:** The academy-platform is already deployed, has authentication, and uses Supabase. Adding bot admin pages is incremental work — a few new routes and components. This also moves toward the Phase 5 goal of unifying the bot and website into a single platform. Shared authentication means one login for both student-facing and admin features.

**Consequences:**
- Tight coupling between bot admin and academy-platform deployment
- Academy-platform must connect to bot's Supabase project (or both projects merged in Phase 5)
- React/TypeScript for admin UI vs Python for bot backend — context switching for developer
- Admin features are available immediately at learnwithaakash.in/admin

---

## Decision: Multi-Platform — Adapter Pattern

**Status:** Accepted

**Context:** The bot currently only works on Telegram. Future plans include Discord and website chat. The core AI logic (prompts, memory, RAG, tools) should not be duplicated per platform.

**Decision:** Implement a **platform adapter pattern**:
- Define platform-agnostic `ChatMessage` and `ChatResponse` contracts
- Thin adapters per platform (Telegram, Discord, Website) that translate platform-specific events to/from the common contracts
- Single FastAPI gateway handles all platforms
- Shared agent service, memory, and tools across all platforms

**Alternatives Considered:**
| Alternative | Pros | Cons |
|---|---|---|
| OpenClaw | Built-in multi-platform | Replaces entire bot architecture, TypeScript, requires Pro plan |
| Separate bots per platform | Simplest per-platform | No shared memory, duplicated logic, inconsistent behavior |
| BotFramework (Microsoft) | Enterprise multi-platform | Heavy, complex, Microsoft ecosystem lock-in |
| Matrix protocol | Open, federated | Niche, complex setup, students unlikely to use Matrix |

**Rationale:** The adapter pattern keeps the core AI logic in one place while allowing each platform to handle its own quirks (Telegram's markdown format, Discord's embeds, website's streaming). Adding a new platform is just writing a thin adapter. Memory and conversation history are shared, so a student can start a conversation on Telegram and continue on the website.

**Consequences:**
- Upfront abstraction work before it's strictly needed (YAGNI risk)
- Message format differences between platforms need careful mapping
- Some platform features (Telegram inline keyboards, Discord threads) may not map cleanly to the common contract
- Testing must cover each adapter independently

---

## ADR-009: RAG Implementation -- Gemini File Search Tool (REVISED)

**Status:** Accepted (supersedes custom RAG pipeline plan)
**Date:** 2026-03-24
**Context:** Originally planned to build a custom RAG pipeline (chunk PDFs -> embed with gemini-embedding-001 -> store in pgvector -> semantic search). Research revealed Google's Gemini File Search Tool, a fully managed RAG system built into the Gemini API.
**Decision:** Use Gemini File Search Tool instead of custom RAG pipeline.
**How it works:**
1. Create a File Search Store
2. Upload PDFs/docs to the store (auto-chunked, auto-embedded, auto-indexed)
3. Query with `generateContent()` passing the File Search Store as a tool
4. Gemini handles retrieval, grounding, and citation automatically

**Code (entire RAG in ~15 lines):**
```python
from google import genai
from google.genai import types

client = genai.Client()
store = client.file_search_stores.create(config={'display_name': 'cbse-notes'})
client.file_search_stores.upload_to_file_search_store(
    file='class10_ai_nlp.pdf',
    file_search_store_name=store.name,
    config={'display_name': 'Class 10 AI NLP Notes'}
)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain NLP in the context of Class 10 AI",
    config=types.GenerateContentConfig(
        tools=[types.Tool(file_search=types.FileSearch(
            file_search_store_names=[store.name]
        ))]
    )
)
```

**Pricing:** Storage and query-time embeddings are FREE. Only pay $0.15/1M tokens for initial indexing.
**Alternatives considered:**
- Custom pipeline (pgvector + gemini-embedding-001): More control but 3 weeks to build
- LightRAG: Good but adds dependency; File Search is simpler
- Vertex AI RAG Engine: Enterprise tier, not free
**Consequences:**
- Phase 3 reduces from 3 weeks to ~1 week
- No need to manage pgvector embeddings for content (still use pgvector for Mem0 memory)
- Content indexed in Google's infrastructure, not local
- Automatic citations from File Search
- Still need Supabase for user data, interactions, memory -- File Search is ONLY for content RAG

---

## ADR-010: PDF Parsing -- IBM Docling (REVISED)

**Status:** Accepted (supersedes PyMuPDF for complex documents)
**Date:** 2026-03-24
**Context:** Need to extract text from CBSE PDFs including tables, diagrams, and structured content. Benchmarks show Docling achieves 97.9% accuracy on table extraction vs PyMuPDF's 80.6%.
**Decision:** Use IBM Docling for PDF text extraction, especially for documents with tables and structured content. Use Gemini 2.5 Flash multimodal for documents with diagrams/images that need visual understanding.
**Details:**
- Docling: MIT license, 56K+ GitHub stars, runs locally, no API key needed
- Outputs clean Markdown/JSON from PDFs
- Handles DOCX, PPTX, XLSX, HTML too
- pip install docling
- Falls back to PyMuPDF for simple text-only PDFs (faster: 0.7ms vs Docling's ~6s)
**Alternatives considered:**
- PyMuPDF only: Fast but misses tables and structure
- Gemini 2.5 Flash only: Best accuracy (88%) but uses API quota
- LlamaParse: Good ($0.003/page) but paid service
**Consequences:**
- Better quality content extraction, especially for CBSE textbook tables
- Local processing, no API costs
- Slightly slower than PyMuPDF but much more accurate
