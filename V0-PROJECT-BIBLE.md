# ASK AI - Project Bible (V0)

> The single source of truth for the ASK AI educational platform. Read this document to understand everything about this project. Last updated: March 24, 2026.

---

## 1. Project Vision

**ASK AI** is an AI-powered educational platform for Indian CBSE students (Classes 10-12) studying AI, CS, IT, and IP. Created by **Aakash Singh** (IIT Bombay alumnus, single developer).

**Current state:** A Telegram study bot that shares Google Drive links to notes/PDFs.
**Target state:** A memory-enabled, content-intelligent, multi-platform learning system that actually teaches.

**Scale:**
- 2,870 unique students, 14,470+ recorded interactions
- 83% returning user rate (exceptional for a bot)
- YouTube channel: ~100K subscribers, ~30M views
- Website: [learnwithaakash.in](https://learnwithaakash.in) (React 19 + Vite + Supabase)
- Telegram group + bot active
- Content: 200+ PDFs across Classes 10-12 for AI, CS, IT, IP

---

## 2. Student Data Analysis

### Dataset
- **Sheet1:** 14,470 interactions (Dec 2024 - Nov 2025) -- older format with screener/intent columns
- **Logs sheet:** 4,134 interactions (Nov 2025+ agent-era) -- newer format with agent responses
- **UserProfiles:** 1,369 registered profiles

### Key Metrics

| Metric | Value |
|--------|-------|
| Total interactions | 14,470 (Sheet1) + 4,134 (Logs) |
| Unique users | 2,870 |
| Registered profiles | 1,369 |
| One-time users | 493 (17%) |
| Returning users (>1 msg) | 2,377 (83%) |
| Power users (>10 msgs) | 258 |
| Top single message | "notes" -- sent 463 times |
| Date range | Dec 5, 2024 to present |

### What Students Ask (Message Categories)

| Category | Count | % | Insight |
|----------|-------|---|---------|
| Notes/PDF requests | 4,122 | 28% | Primary use case -- bot is a file server today |
| Class identification | 5,031 | 34% | "class 10 AI" etc -- setting context |
| Exam/paper requests | 729 | 5% | Sample papers, PYQs -- high intent |
| Explanation requests | 555 | 3% | "explain X", "what is Y" -- THE opportunity for RAG |
| Video requests | 372 | 2% | Searching for tutorial videos |
| Project requests | 225 | 1% | Practical/project help |
| Help/doubt requests | 155 | 1% | "I'm confused", "stuck on..." -- needs Socratic method |
| Greetings | 403 | 2% | "hi", "hello" |

### What the Bot Does (Response Patterns)

| Response Type | % | Problem? |
|---------------|---|----------|
| Sends Drive links | 29% | Links bounce students to Drive -- context switch kills engagement |
| Profile updates | 21% | "Updated class to 10" -- necessary but not valuable |
| Asks for more info | 14% | "Which class? Which subject?" -- BROKEN: should use profile |
| Can't find content | 14% | Content gaps or search failures -- lost students |
| Longer explanations | 6% | Actual substantive answers -- the goal |
| Greetings | 3% | -- |

### Class and Subject Distribution

**From UserProfiles (1,369):**
- Class 10: 547 (40%), Class 11: 140 (10%), Class 12: 108 (8%), **Unset: 574 (42%!)**
- AI: 553, CS: 141, IT: 46, IP: 37, **Unset: 590**

**From message analysis (14,470):**
- Class 10: 2,719 mentions (dominant)
- Class 11: 1,007
- Class 12: 863
- AI: 2,526, IT: 1,299, CS: 700, IP: 335, Python: 234

### Three Biggest UX Problems
1. **14% "please specify" responses** even when the user profile already has class/subject set
2. **42% of registered users never set their class/subject** -- onboarding is broken
3. **14% "can't find content"** -- content gaps or poor search matching

### Sample Explanation Requests (what RAG would serve)
- "what is confusing matrix" (confusion matrix)
- "explain e spreadsheet with video and notes"
- "I am confused on how to start my AI 417 preparation"
- "what are jump statements in python explain with example"
- "how to cover 10 cbse syllabus in 2 months"
- "please explain me degital documentation"
- "can you please explain me dbms"

---

## 3. Persona Analysis

### Persona 1: Senior UI/UX Researcher
> "14% of responses are 'please specify class/subject.' That is a broken flow. 42% of registered users never set their class. The onboarding is failing. Memory fixes this -- once a student says 'Class 10 AI' one time, they should NEVER be asked again. 28% of interactions end with a Drive link -- students are bouncing to Google Drive mid-conversation. That context switch kills engagement."

### Persona 2: Senior Educational Researcher (Oxford, 25 years)
> "Only 3% of interactions are explanation requests, yet THIS is where learning happens. The bot has trained students to treat it as a file server, not a tutor. With RAG and memory, conceptual questions like 'what is confusing matrix' or 'explain jump statements in python' would get actual answers. The real questions ARE there -- 'how to cover 10 CBSE syllabus in 2 months', 'I am confused on how to start my AI 417 preparation' -- these are metacognitive cries for help that a memory-enabled tutor could address brilliantly. Bloom's Two Sigma Problem remains unsolved; memory-enabled AI is the first realistic path to solving it at scale."

### Persona 3: AI Consultant
> "You are paying for OpenAI but using Gemini in the academy platform's content_agent. The academy platform already has Supabase with PostgreSQL. The bot uses Google Sheets. These need to converge: one embedding model (Gemini, free), smart LLM routing (GPT-4o for quality, Gemini Flash for simple queries). The pieces exist, they are just not connected."

### Persona 4: EdTech CEO
> "83% returning users is exceptional. That means students WANT to come back. But 14% 'can't find content' responses mean you are losing them. Every 'content not found' is a student who may not return. Fix content discovery first, then layer memory for retention. The 258 power users with 10+ messages are your champions -- memory would make them evangelists. Nobody is doing memory-first tutoring for Indian CBSE students well."

### Persona 5: Enterprise AI Architect
> "Google gives you free: Gemini 2.5 Flash (250 RPD, 250K TPM), Gemini Embedding (free tier), and native PDF understanding (up to 1000 pages). You are paying OpenAI for embeddings when Google offers them free. The adapter pattern achieves multi-platform without throwing away the codebase."

### Persona 6: Agentic Framework Specialist
> "The bot's tool architecture (BaseTool, register_tool, function-calling) is clean and extensible. Adding a memory tool and RAG tool to the existing registry requires no structural changes. The AGENT_SQLITE_PATH placeholder shows you planned for persistence. Now that the academy platform uses Supabase, that is the right shared backend."

---

## 4. Current Architecture

### Stack
- **Framework:** FastAPI + python-telegram-bot v21
- **LLM:** OpenAI GPT-4o via Responses API with function-calling
- **Storage:** Google Sheets (profiles, logs, notes index, folders, warnings)
- **Content:** Google Drive (200+ PDFs: Class > Subject > Type > Topic)
- **Memory:** In-memory dict (`AgentService.conversation_history`), capped at 20 messages, lost on restart
- **Deployment:** Google Cloud Run + Secret Manager, webhook via FastAPI `/webhook`

### Tools
| Tool | Function | Description |
|------|----------|-------------|
| `get_notes` | NotesTool | Returns Drive folder links for class/subject/topic |
| `list_available_resources` | ListResourcesTool | Shows what's available for a class |
| `search_videos` | VideosTool | YouTube channel search |
| `update_user_profile` | ProfileTool | Updates class/subject in profile |
| `web_search_preview` | Built-in | OpenAI native web search |

### Key Files
| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, webhook endpoint |
| `telegram_bot/application.py` | Wiring, DI, tool registration |
| `telegram_bot/handlers.py` | Message routing (private vs group) |
| `telegram_bot/services/agent_service.py` | OpenAI Responses API orchestration |
| `telegram_bot/prompts/agent_system.md` | System prompt ("ASK.ai, friendly study buddy") |
| `telegram_bot/services/user_service.py` | Google Sheets user profiles |
| `telegram_bot/services/note_service.py` | Note retrieval from Sheet index |
| `telegram_bot/services/sync_service.py` | Drive -> Sheet sync (every 5 min) |
| `telegram_bot/services/group/group_orchestrator.py` | Group chat handling |
| `telegram_bot/services/moderation/content_moderator.py` | GPT-4o-mini content moderation |
| `config/settings.py` | All config including unused AGENT_SQLITE_PATH, RETRIEVER_STORE_PATH |

### Data Flow
```
Telegram -> FastAPI /webhook -> Application.process_update
  -> handlers.handle_message
    -> Private: ContentModerator.check -> AgentService.process -> send_response
    -> Group: GroupOrchestrator (moderation + optional agent) -> reply
AgentService.process:
  -> Build system prompt (PromptFactory)
  -> Add conversation history (in-memory, capped)
  -> Call OpenAI Responses API with tools
  -> Execute function calls (tools)
  -> Return response
  -> Log to Google Sheets
```

### What's NOT Built (placeholder configs exist)
- `AGENT_SQLITE_PATH` in settings.py -- unused, no SQLite anywhere
- `RETRIEVER_STORE_PATH` in settings.py -- unused, no vector store
- `EMBEDDING_MODEL` in settings.py -- unused, no embeddings
- `infrastructure/file_note_repository.py` -- alternate repository, unused

---

## 5. Target Architecture

### Smart LLM Routing
- **GPT-4o:** Doubts, explanations, conceptual questions, board exam answers (quality matters)
- **Gemini 2.5 Flash (FREE):** Notes requests, link retrieval, greetings, simple queries
- **Routing:** Keyword detection -- "explain", "what is", "how does" -> GPT-4o; "notes", "pdf", "link" -> Gemini Flash

### Database: Supabase PostgreSQL (Separate Project)
- Not shared with academy-platform (isolation)
- pgvector extension for embeddings
- Tables: bot_users, bot_interactions, content_index, folders, bot_warnings

### Embeddings: gemini-embedding-001 (FREE)
- 3072 dimensions (MRL: scalable down to 768)
- Free tier available
- Paid: $0.15/1M tokens

### Memory: Mem0 (Self-hosted)
- Python-native (`pip install mem0ai`)
- Supabase pgvector backend
- gemini-embedding-001 for memory embeddings (FREE)
- GPT-4o-mini for memory extraction (cheap)

### Document Parsing: Gemini 2.5 Flash (FREE)
- Multimodal: understands tables, diagrams, charts, layouts
- Up to 1000 pages per PDF
- Free tier: 10 RPM, 250K TPM, 250 RPD

### Content Sources
1. Google Drive PDFs (existing 200+ files)
2. YouTube video transcripts (100+ videos)
3. Custom notes/PDFs uploaded by admin
4. NCERT/CBSE textbook content

---

## 6. Technology Decision Records

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary LLM | Smart routing: GPT-4o + Gemini Flash | Quality for doubts, free for simple queries |
| Database | Supabase PostgreSQL (separate project) | Real DB, pgvector built-in, free tier sufficient |
| Embeddings | gemini-embedding-001 | FREE, 3072 dims, state-of-the-art |
| Vector store | Supabase pgvector | Built into PostgreSQL, no separate service |
| Memory | Mem0 self-hosted | Python-native, free, 50K+ stars |
| Doc parsing | Gemini 2.5 Flash | FREE, multimodal, already used in content_agent |
| Admin dashboard | Extend academy-platform | Already has admin pages, React + Supabase |
| Multi-platform | Adapter pattern | Thin adapters, shared gateway |
| Content RAG | Gemini File Search Tool | Fully managed RAG, FREE storage/queries, eliminates custom pipeline |
| PDF parsing | IBM Docling + PyMuPDF fallback | 97.9% table accuracy, local, MIT license |

**Why NOT OpenClaw/Supermemory:** TypeScript ecosystem mismatch, requires Pro plan, would replace bot not enhance it. Borrowed design patterns (auto-recall, auto-capture, container tags) for Mem0 instead.

---

## 7. Academic Research Summary

| Paper | Key Finding |
|-------|-------------|
| **Jarvis** (SSRN 2025) | Cognitive memory architecture for AI-augmented learning. Persistent memory + metacognition + emotional tracking + spaced repetition. Neurodivergent learner completed 39 credits using it. |
| **LOOM** (arXiv 2511.21037) | Dynamic Learner Memory Graph. Conversation summarization -> topic planning -> course generation -> graph-based progress tracking. |
| **TASA** (arXiv 2511.15163) | Persona + Memory + Forgetting-aware tutoring. Forgetting curves + knowledge tracing = superior learning outcomes. |
| **Nature 2025 RCT** | AI tutoring outperformed in-class active learning. Students learned more in less time. Key variable: personalization. |
| **UK Classroom RCT** (arXiv 2512.23633) | AI tutoring safely and effectively supports students when properly designed. |
| **Memoria** (arXiv 2512.12686) | Hybrid: dynamic session summarization + weighted knowledge graph for user traits/preferences. |

**Five Layers of Educational Memory:**
```
Layer 5: METACOGNITIVE  -- "Student confuses velocity with acceleration"
Layer 4: FORGETTING      -- "12 days since derivatives; likely fading"
Layer 3: KNOWLEDGE STATE -- "Mastered: algebra. In-progress: calculus. Gap: trig"
Layer 2: EPISODIC        -- "Last Tuesday asked about quadratic formula, got it on 3rd try"
Layer 1: CONVERSATIONAL  -- "In this session, discussing Chapter 5"
```
Current bot has only Layer 1 (and loses it on restart). Target: Layers 1-3 minimum.

---

## 8. Google Free Tier Research

| Service | Free Tier | Our Usage | Sufficient? |
|---------|-----------|-----------|-------------|
| Gemini 2.5 Flash | 10 RPM, 250K TPM, 250 RPD | ~20 PDFs/day ingestion, 0 at runtime | Yes |
| Gemini 2.5 Pro | 5 RPM, 250K TPM, 100 RPD | Not primary model | Yes |
| gemini-embedding-001 | Free tier | ~10K embeddings one-time | Yes |
| Gemini 3 Flash Preview | Free tier | Potential future upgrade | Yes |
| Supabase Spark | 500MB, 50K MAU | ~50MB data, 3K MAU | Yes |

**Estimated additional monthly cost after all phases: $0** (beyond existing OpenAI spend)

---

## 9. Academy Platform (learnwithaakash.in)

- **Stack:** React 19 + Vite SPA, Tailwind CSS, Framer Motion, Three.js
- **Backend:** Supabase (Auth + PostgreSQL), Vercel Python API (FastAPI)
- **Content:** `content_agent/` -- PyMuPDF + Gemini for PDF -> course content
- **AI Tutor:** `useAITutor.js` -> POST /api/chat -> OpenAI (stateless)
- **Progress:** XP, streaks, badges via ProgressContext (localStorage only)
- **Admin:** Pages at /admin/* (users, courses, lesson editor, question bank)
- **Auth:** Supabase Auth (Google OAuth + email/password)
- **Theme:** Dark "Cyberpunk Ivy League" (Outfit + Inter fonts)
- **Deploy:** Vercel, auto-deploy on push to main

---

## 10. Implementation Roadmap

| Phase | Scope | Duration | Key Deliverable |
|-------|-------|----------|-----------------|
| 0 | Quick fixes | Day 1 | Fix is_admin, onboarding, profile defaults |
| 1 | Supabase migration | Week 1-2 | All data in PostgreSQL, Sheets deprecated |
| 2 | Memory layer | Week 3-4 | Mem0 + /memory + /forget |
| 3 | Content RAG | Week 5-7 | Doubt answering from actual content |
| 4 | Smart features | Week 7-9 | Board prep, quiz, study planner, video notes |
| 5 | Website unify | Week 9-11 | Shared memory with website, admin dashboard |
| 6 | Advanced | Week 11+ | Spaced repetition, knowledge graph, multi-platform |

---

## 11. Plan Documents

All detailed plans are in `.cursor/plans/`:
- `00-master-overview.md` -- Phase dependency graph and timeline
- `01-phase-0-quick-fixes.md` through `07-phase-6-advanced.md` -- Individual phase specs
- `features-backlog.md` -- Full feature list with P0-P3 priorities
- `technology-decisions.md` -- Architecture Decision Records
- `guardrails-spec.md` -- CBSE alignment, Socratic method, citation rules
- `skills-setup.md` -- Development tools and plugin installation

---

## 12. Development Skills

**Installed:**
- feature-dev: 7-phase guided feature development
- GSD: Spec-driven dev with context engineering
- pm-skills: PRDs, sprint planning, user personas
- claude-code-setup: Codebase analysis and recommendations
- supabase: DB operations MCP
- security-guidance: Security-sensitive edit warnings
- playground: Interactive HTML demos

**To set up:** Linear (free issue tracking) -- see skills-setup.md

---

## 13. Key References

| Resource | URL |
|----------|-----|
| Mem0 GitHub | https://github.com/mem0ai/mem0 |
| Gemini API Pricing | https://ai.google.dev/gemini-api/docs/pricing |
| Gemini Embeddings | https://ai.google.dev/gemini-api/docs/embeddings |
| Gemini Document Understanding | https://ai.google.dev/gemini-api/docs/document-processing |
| Supabase pgvector | https://supabase.com/docs/guides/ai/vector-columns |
| Jarvis Paper | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5218379 |
| LOOM Paper | https://arxiv.org/abs/2511.21037 |
| TASA Paper | https://arxiv.org/abs/2511.15163 |
| Nature AI Tutoring RCT | https://www.nature.com/articles/s41598-025-97652-6 |
| UK Classroom RCT | https://arxiv.org/abs/2512.23633 |
| Duolingo LLM Architecture | https://architecturallyspeaking.substack.com/p/case-study-how-duolingo-scaled-content |
| Khanmigo Blog | https://blog.khanacademy.org/how-we-built-ai-tutoring-tools/ |
| Platform Adapter Pattern | https://amiable.dev/blog/luminescent-cluster/05-multi-platform-chatbots/ |
| Firebase + AI Studio | https://firebase.blog/posts/2026/03/announcing-ai-studio-integration |
| Firestore Vector Search | https://firebase.google.com/docs/firestore/vector-search |

---

## 15. Technology Updates (Post-V0)

> Decisions made after the initial V0 planning session. See DECISIONS.md for the full changelog.

### Gemini File Search Tool (Game-Changer Discovery)
Google's Gemini API includes a **fully managed RAG system** called File Search. It handles chunking, embedding, indexing, and retrieval automatically. Storage and query-time embeddings are FREE. This eliminates the need to build a custom RAG pipeline (pgvector + embedding + search).

**Impact on Phase 3:** Reduces from 3 weeks to ~1 week. Instead of building: chunk -> embed -> store -> search -> retrieve, we just: upload PDF -> query with File Search tool.

**What this means for the architecture:**
- Supabase pgvector is STILL needed for Mem0 (student memory)
- File Search handles content RAG (notes, PDFs, YouTube transcripts)
- Two vector stores: Gemini File Search (content) + Supabase pgvector (memory)

### IBM Docling for PDF Parsing
IBM's open-source document parser (56K+ GitHub stars, MIT license). Achieves 97.9% accuracy on table extraction. Runs locally, no API costs. Outputs clean Markdown/JSON.

**Replaces:** PyMuPDF for structured documents (tables, formatted content). PyMuPDF kept as fast fallback for simple text PDFs.

### Libraries to Avoid Rebuilding
| Need | Library | Saves |
|------|---------|-------|
| RAG pipeline | Gemini File Search Tool | Entire custom RAG implementation (~3 weeks) |
| PDF parsing | IBM Docling + PyMuPDF (fallback) | Custom table/structure extraction |
| YouTube transcripts | youtube-transcript-api | Subtitle extraction |
| Memory layer | mem0ai | Custom memory system |
| Spaced repetition | fsrs (Python) | Forgetting curve math |
| Gemini SDK | google-genai | Embeddings, file search, content generation |

### Solo Developer Practices
- 2-week cycles with 2-3 deliverables each
- One session = one committable, testable change
- Feature flags for migrations (run both systems in parallel)
- Ship to production every phase (don't accumulate)
- 20% buffer on all estimates
- Energy management: complex work in peak hours

---

## 16. Development Workflow Guide

> How GSD, feature-dev, and PM skills work together. Read this section BEFORE starting any phase.

### The Three Systems and When to Use Each

**GSD (Get Shit Done) -- 57 skills: Your execution engine.**
Manages the full lifecycle of a phase: discuss requirements, generate plans, execute in parallel waves, verify, ship. Think of it as "the project manager that keeps you on track across sessions."

**feature-dev -- 1 skill: Your deep-dive engineering tool.**
When you hit a complex feature INSIDE a phase (e.g., designing the memory recall/capture flow), feature-dev does 7 focused steps: discover what's needed, explore the codebase with parallel agents, ask clarifying questions, generate multiple architecture options, implement after you approve, review with parallel agents, summarize.

**PM skills -- 27 skills: Your product thinking tools.**
For the moments when you need to step back and think about WHAT to build (not HOW). Write PRDs, define user personas from your student data, prioritize features, set metrics.

### Decision Tree: Which Tool for What

```
"I'm starting Phase N from scratch"
  → GSD: gsd-discuss-phase → gsd-plan-phase → gsd-execute-phase → gsd-verify-work

"I need to define WHAT this feature should do before building"
  → PM: pm-create-prd (writes a full Product Requirements Document)

"I'm inside a phase, facing a complex multi-file feature"
  → feature-dev (7-phase: discover → explore → clarify → architect → implement → review → summary)

"I need to prioritize which features to build first"
  → PM: pm-prioritize-features (RICE, ICE, Kano, MoSCoW frameworks)

"Quick bug fix or trivial change"
  → GSD: gsd-fast (zero ceremony, just do it)

"Small task, but want some structure"
  → GSD: gsd-quick (optional --discuss, --research, --full flags)

"I don't know which GSD command to use"
  → GSD: gsd-do (describe what you want in plain English, it picks the right command)

"I want to understand my students better"
  → PM: pm-user-personas (from the 14,470-interaction dataset)

"I need to set up metrics for the admin dashboard"
  → PM: pm-metrics-dashboard + pm-north-star-metric

"Something is broken and I can't figure out why"
  → GSD: gsd-debug (systematic debugging with state tracking)

"I lost context from last session"
  → Read .cursor/rules/ask-ai-project.mdc (auto-loaded) + this V0 Bible
  → GSD: gsd-resume-work (picks up where you left off)
```

### Recommended Flow for Each Phase

**Phase 0 (Quick Fixes):**
1. Just use `gsd-fast` for each of the 3 fixes. No ceremony needed.

**Phases 1-6 (Substantial Work):**
1. **Read the phase plan** in `.cursor/plans/0N-phase-*.md`
2. **Optional:** Run `pm-create-prd` if the phase spec needs more detail
3. Run `gsd-discuss-phase N` to capture your vision and decisions
4. Run `gsd-plan-phase N` to generate implementation tasks
5. Run `gsd-execute-phase N` to implement (uses parallel waves for independent tasks)
6. For complex sub-features within the phase, use `feature-dev` for deep exploration + architecture
7. Run `gsd-verify-work N` to check everything works
8. Ship and deploy

**Between Sessions:**
- GSD tracks state in `.planning/STATE.md` -- auto-resumable
- `gsd-resume-work` picks up exactly where you left off
- `gsd-check-todos` shows what's pending
- `gsd-progress` shows overall status

### GSD Commands Mapped to Your Phases

| Your Phase | Primary GSD Commands | When to Use feature-dev |
|------------|---------------------|------------------------|
| Phase 0: Quick fixes | `gsd-fast` (x3) | Not needed |
| Phase 1: Supabase migration | `discuss → plan → execute → verify` | Schema design, dual-write cutover strategy |
| Phase 2: Memory layer | `discuss → plan → execute → verify` | Mem0 integration design, memory-aware prompting |
| Phase 3: Content RAG | `discuss → plan → execute → verify` | Gemini File Search integration, smart LLM routing logic |
| Phase 4: Smart features | `discuss → plan → execute → verify` | Each feature individually (quiz, planner, doubt solver) |
| Phase 5: Website unify | `discuss → plan → execute → verify` | Account linking flow, shared memory architecture |
| Phase 6: Advanced | `discuss → plan → execute → verify` | Spaced repetition algorithm, adapter pattern |

### PM Skills: When to Use Them

| Moment | PM Skill | Output |
|--------|----------|--------|
| Before Phase 1 starts | `pm-create-prd` | Full PRD for the Supabase migration |
| Before Phase 3 starts | `pm-create-prd` | Full PRD for the RAG/doubt-solving system |
| Before Phase 4 starts | `pm-prioritize-features` | Ordered list of which smart features to build first |
| When designing the admin dashboard | `pm-metrics-dashboard` | What metrics to track, alert thresholds |
| When defining student segments | `pm-user-personas` | 3 personas from real data (note-seeker, doubt-solver, exam-prepper) |
| When thinking about monetization | `pm-lean-canvas` | Business model canvas |
| When planning a launch (Discord, website) | `pm-gtm-strategy` | Go-to-market plan |
| After each phase ships | `pm-retro` | What went well, what didn't, actions |

### Installed Skills Quick Reference

**90 total skills in `.cursor/skills/`:**

| Category | Count | Key Skills |
|----------|-------|------------|
| GSD | 57 | `gsd-do`, `gsd-fast`, `gsd-quick`, `gsd-discuss-phase`, `gsd-plan-phase`, `gsd-execute-phase`, `gsd-verify-work`, `gsd-debug`, `gsd-resume-work`, `gsd-progress`, `gsd-new-project`, `gsd-ship` |
| PM | 27 | `pm-create-prd`, `pm-sprint-plan`, `pm-user-personas`, `pm-prioritize-features`, `pm-metrics-dashboard`, `pm-north-star-metric`, `pm-pre-mortem`, `pm-brainstorm-okrs`, `pm-product-strategy` |
| Engineering | 6 | `feature-dev`, `claude-code-setup`, `security-guidance`, `supabase`, `playground`, `linear` |

### Context Preservation: How It All Stays Connected

```
.cursor/rules/ask-ai-project.mdc    ← Auto-loaded EVERY session (project context)
.cursor/rules/decision-logger.mdc   ← Auto-reminds to log architecture changes
V0-PROJECT-BIBLE.md                 ← This file (full research, read when lost)
DECISIONS.md                        ← Immutable decision log (append-only)
.cursor/plans/*.md                  ← Phase specs (read before executing a phase)
.planning/STATE.md                  ← GSD's auto-tracked execution state
Linear                              ← Issue tracking across weeks (free, 250 issues)
```

### Estimated Timeline (Realistic, Single Developer)

| Phase | Optimistic | Realistic | What Could Delay It |
|-------|-----------|-----------|---------------------|
| Phase 0: Quick fixes | 1 day | 2 days | Nothing |
| Phase 1: Supabase migration | 1 week | 2 weeks | Data validation, dual-write testing |
| Phase 2: Memory (Mem0) | 1 week | 2 weeks | Mem0 pgvector config, prompt tuning |
| Phase 3: Content RAG | 1 week | 2 weeks | Gemini File Search simplifies this massively |
| Phase 4: Smart features | 2 weeks | 3 weeks | Prompt engineering for CBSE format |
| Phase 5: Website unify | 2 weeks | 3 weeks | Two repos, account linking |
| Phase 6: Advanced | 3 weeks | 4+ weeks | Spaced repetition, multi-platform |
| **Total** | **~11 weeks** | **~16 weeks** | |

**Most impactful milestone:** Phase 3 complete -- bot transforms from file server to tutor.

### Things to Watch Out For

1. **Gemini free tier limits:** 250 RPD for Flash. Batch PDF ingestion over multiple days.
2. **Embedding dimensions:** Start with 768 (saves storage). Document this in DECISIONS.md.
3. **Mem0 version:** Pin in requirements.txt. Test memory recall quality before shipping.
4. **Supabase free tier:** 500MB storage. Monitor as content embeddings grow.
5. **Prompt length:** As you add memory + RAG + guardrails, prompts get long. Test with both GPT-4o and Gemini Flash.
6. **The UX shift:** Students trained to say "notes" will need a nudge: "I can now explain topics directly! Try 'explain NLP'."
7. **YouTube transcripts:** Hindi videos may have poor auto-generated transcripts. Test with your actual channel.
8. **CBSE curriculum updates:** Add a "last validated" date to content index. Flag stale content in admin dashboard.

---

*This document was generated from an intensive research and planning session. It captures analysis of 14,470 student interactions, review of 6+ academic papers, evaluation of multiple technology options, and strategic thinking from 6 distinct professional perspectives. It should be treated as the authoritative reference for all development decisions on the ASK AI platform.*
