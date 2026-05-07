# ASK AI - Feature Backlog

**Last Updated:** 2026-03-24
**Total Features:** 37
**Format:** ID | Name | Description | Phase | Priority | Dependencies | Effort

---

## P0 - Must Have (Core Platform)

These features form the foundation. Without them, the platform cannot evolve beyond a file-serving bot.

| ID | Name | Description | Phase | Priority | Dependencies | Effort |
|----|------|-------------|-------|----------|--------------|--------|
| F-001 | Supabase Migration | Migrate all data from Google Sheets to Supabase PostgreSQL. Includes bot_users, interaction_logs, notes_index, warnings tables. | Phase 1 | P0 | None | XL |
| F-002 | Persistent Memory (Mem0) | Add Mem0 with Supabase pgvector backend so the bot remembers student context (class, subject, past questions) across sessions. Eliminates 14% "please specify class" responses. | Phase 2 | P0 | F-001 | L |
| F-003 | Doubt Solving RAG | Parse Drive PDFs + NCERT content into vector store. When a student asks a question, retrieve relevant chunks and generate accurate, cited answers. | Phase 3 | P0 | F-001, F-002 | XL |
| F-004 | Smart LLM Routing | Route messages to appropriate model: GPT-4o for doubts/explanations, Gemini 2.5 Flash (free) for notes requests/greetings/links. Reduces API costs by ~60%. | Phase 3 | P0 | F-003 | M |
| F-005 | Content Ingestion Pipeline | Automated pipeline: PDF upload -> Gemini parsing -> chunking -> embedding -> pgvector storage. Support for Drive sync and manual upload. | Phase 3 | P0 | F-001 | L |
| F-006 | Fix Onboarding Flow | Guided first-interaction flow that collects class and subject before anything else. Reduce 42% incomplete profiles to <5%. Default to Class 10 AI if abandoned. | Phase 0 | P0 | None | S |
| F-007 | Fix is_admin Bug | Admin check currently broken. Fix the admin detection logic so admin-only commands work correctly. | Phase 0 | P0 | None | S |

---

## P1 - Should Have (Key Differentiators)

These features differentiate ASK AI from a generic chatbot and make it genuinely useful for CBSE exam prep.

| ID | Name | Description | Phase | Priority | Dependencies | Effort |
|----|------|-------------|-------|----------|--------------|--------|
| F-008 | Board Exam Answer Format | Auto-detect question type (1/2/3/5 mark) and format answers accordingly with proper structure, marks allocation, and model-answer style. | Phase 4 | P1 | F-003 | M |
| F-009 | YouTube Video Notes Generation | Generate structured notes from YouTube video transcripts. Student sends a video link, bot returns chapter-wise notes with timestamps. | Phase 4 | P1 | F-005 | L |
| F-010 | Source Citation in Answers | Every RAG-sourced answer includes citation: PDF name, chapter, class/subject. Web search answers clearly marked as external. Builds trust and verifiability. | Phase 3 | P1 | F-003 | M |
| F-011 | Admin Content Upload Dashboard | Web UI for admin to upload PDFs, preview parsed chunks, approve/reject before indexing. No more manual Drive uploads. | Phase 5 | P1 | F-005, Phase 5 | L |
| F-012 | Student Usage Analytics | Admin dashboard showing: active users/day, top queries, content gaps, subject distribution, response quality metrics. | Phase 5 | P1 | F-001, Phase 5 | L |
| F-013 | Memory Commands (/memory, /forget) | `/memory` shows what the bot remembers about the student. `/forget` lets students delete specific memories. Transparency and control. | Phase 2 | P1 | F-002 | S |

---

## P2 - Nice to Have (Growth Features)

These features increase engagement, retention, and platform stickiness.

| ID | Name | Description | Phase | Priority | Dependencies | Effort |
|----|------|-------------|-------|----------|--------------|--------|
| F-014 | Quiz Mode (MCQ Generation) | Generate topic-specific MCQs from indexed content. Timed quizzes with scoring, explanations for wrong answers. Supports active recall. | Phase 4 | P2 | F-003 | L |
| F-015 | Study Planner | AI-generated study plans based on exam date, syllabus coverage, and student's mastery levels. Daily/weekly task breakdown. | Phase 4 | P2 | F-003, F-002 | L |
| F-016 | Website Learning Dashboard | Visual progress page: topics studied, strengths/weaknesses radar, activity timeline, conversation history. | Phase 5 | P2 | Phase 5, F-002 | L |
| F-017 | Account Linking (Telegram <-> Website) | `/link` command generates one-time code to connect Telegram account with website login. Enables cross-platform experience. | Phase 5 | P2 | F-001, Phase 5 | M |
| F-018 | Admin Memory Browser | Web UI to search and view any student's Mem0 memories. Delete incorrect/outdated memories. Audit trail. | Phase 5 | P2 | F-002, Phase 5 | M |
| F-019 | Admin Prompt Editor | Edit system prompts from the web UI with version history and instant rollback. No more deploying for prompt changes. | Phase 5 | P2 | Phase 5 | M |
| F-020 | PYQ Practice Mode | Serve actual previous year questions (from indexed content) by topic/year. Show model answers and marking scheme. | Phase 4 | P2 | F-003 | M |
| F-021 | Group Chat Intelligence | Smarter group behavior: only respond when relevant, summarize long threads, detect and answer unanswered questions. | Phase 4 | P2 | F-002, F-003 | M |
| F-022 | Content Gap Detection | Automatically identify topics students ask about but have no indexed content for. Generate report for admin to prioritize content creation. | Phase 3 | P2 | F-003 | M |

---

## P3 - Future (Moonshots)

Long-term vision features that require the full platform to be in place.

| ID | Name | Description | Phase | Priority | Dependencies | Effort |
|----|------|-------------|-------|----------|--------------|--------|
| F-023 | Spaced Repetition Reminders | SM-2 algorithm tracks what students studied and when. Proactive Telegram reminders when topics are due for review. | Phase 6 | P3 | F-002, F-014 | L |
| F-024 | Knowledge Graph Per Student | Visual knowledge map showing mastery across all CBSE topics. Color-coded tree view, radar chart, heatmap calendar. | Phase 6 | P3 | F-023, Phase 5 | XL |
| F-025 | Discord Adapter | discord.py-based adapter sharing the same agent service, memory, and content. Platform-agnostic message contracts. | Phase 6 | P3 | Phase 5 | L |
| F-026 | Website Chat Widget | WebSocket-based chat widget on academy platform. Real-time conversation with same AI tutor as Telegram. | Phase 6 | P3 | Phase 5, F-017 | L |
| F-027 | Voice Message Support | Accept voice messages on Telegram, transcribe with Whisper API, process as text query, respond with text + optional TTS. | Future | P3 | F-003 | M |
| F-028 | Image/Diagram Recognition | Accept photos of textbook pages, diagrams, or handwritten questions. Use GPT-4o vision to understand and respond. | Future | P3 | F-003 | M |
| F-029 | School LMS Integration | API integrations with popular Indian school LMS platforms (Google Classroom, Teachmint, etc.) for assignment sync. | Future | P3 | Phase 5 | XL |
| F-030 | Appeal System for Bans | Banned/warned students can appeal via bot. Appeals reviewed by admin on dashboard. Fairness and transparency. | Future | P3 | F-001, Phase 5 | M |
| F-031 | Rate Limiting Per User | Configurable per-user message limits (e.g., 50 messages/day for free tier). Prevents abuse and manages API costs. | Future | P3 | F-001 | S |
| F-032 | Multilingual Support (Hindi) | Detect Hindi messages and respond in Hindi. Bilingual CBSE content indexing. | Future | P3 | F-003 | L |
| F-033 | Exam Countdown & Reminders | Configurable exam date. Daily countdown, intensifying study reminders as exam approaches. "30 days to boards!" | Future | P3 | F-015 | S |
| F-034 | Collaborative Study Groups | Students can form study groups. Bot facilitates group quizzes, discussion prompts, and peer learning. | Future | P3 | Phase 6 | XL |
| F-035 | Teacher Dashboard | Separate role for teachers: see their students' progress, assign topics, get class-level analytics. | Future | P3 | Phase 5, F-024 | XL |
| F-036 | Offline Content Packs | Generate downloadable PDF study packs customized to student's weak topics. Available when internet is limited. | Future | P3 | F-003, F-024 | L |
| F-037 | Achievement & Streak System | Gamification: study streaks, badges for mastery, leaderboards (opt-in). Motivation through positive reinforcement. | Future | P3 | F-024 | M |

---

## Effort Legend

| Size | Time Estimate | Description |
|------|--------------|-------------|
| **S** | 1-2 days | Single file change, isolated logic, no new infrastructure |
| **M** | 3-5 days | Multiple files, some new logic, may need new table or API |
| **L** | 1-2 weeks | New service/feature, database changes, multiple integrations |
| **XL** | 2-4 weeks | Major system component, significant architecture work, extensive testing |

---

## Phase Summary

| Phase | Features | Effort Range |
|-------|----------|-------------|
| Phase 0 | F-006, F-007 | 2-4 days |
| Phase 1 | F-001 | 2-4 weeks |
| Phase 2 | F-002, F-013 | 1-2 weeks |
| Phase 3 | F-003, F-004, F-005, F-010, F-022 | 4-8 weeks |
| Phase 4 | F-008, F-009, F-014, F-015, F-020, F-021 | 4-8 weeks |
| Phase 5 | F-011, F-012, F-016, F-017, F-018, F-019 | 3-5 weeks |
| Phase 6 | F-023, F-024, F-025, F-026 | 4-8 weeks |
| Future | F-027 through F-037 | Ongoing |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-24 | Backlog created | Initial prioritization based on student data analysis (14,470 interactions) |
| -- | P0 prioritizes memory + DB | 14% of responses are "please specify class" -- memory eliminates this |
| -- | RAG before quiz mode | Only 3% of interactions are explanations -- RAG will unlock this use case |
| -- | Website unification after core | Bot must be independently excellent before cross-platform |
