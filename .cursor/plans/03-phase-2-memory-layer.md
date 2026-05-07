# Phase 2: Persistent Memory Layer

**Duration:** Week 3-4  
**Dependencies:** Phase 1 (Supabase must be set up for pgvector backend)  
**Technology:** mem0ai, gemini-embedding-001 (FREE), Supabase pgvector  

---

## User Stories

### US-2.1: Cross-Session Memory
> As a returning student, the bot should remember what I studied last week.

**Problem:** The bot uses an in-memory dict that's wiped on every Cloud Run restart (happens daily or on deploy). A student who spent 30 minutes discussing Neural Networks yesterday starts from zero today. This kills the tutoring experience — a real tutor would remember.

### US-2.2: Memory Transparency
> As a student, I should be able to see what the bot remembers about me (/memory).

**Problem:** Students have no visibility into what the bot "knows" about them. Transparency builds trust and lets students correct wrong information.

### US-2.3: Data Deletion
> As a student, I should be able to delete my data (/forget).

**Problem:** No mechanism for students to exercise data control. Required for responsible AI and potential compliance.

### US-2.4: Session Continuity
> As a student, I should not have to re-introduce myself every session.

**Problem:** Students currently re-state their class, subject, and topic every session. This friction drives the 14% "please specify" rate and trains students to treat the bot as stateless.

---

## Acceptance Criteria

### AC-1: Mem0 Integration
- [ ] Mem0 configured with Supabase pgvector as vector store
- [ ] gemini-embedding-001 as embedding model (free tier, 3072 dims scaled to 768)
- [ ] Memory operations are async and non-blocking
- [ ] Graceful degradation: if Mem0 fails, bot works without memory

### AC-2: Memory Recall
- [ ] Before each AI response, retrieve top 5 relevant memories for the user
- [ ] Memories injected into system prompt under `## What I Remember About You`
- [ ] Relevance filtering: only inject memories related to current conversation topic
- [ ] Recall latency < 200ms (pgvector with HNSW index)

### AC-3: Memory Capture
- [ ] After each exchange, extract key facts worth remembering
- [ ] Educational memory design (see Memory Categories below)
- [ ] Deduplication: don't store "user is in class 10" fifty times
- [ ] Rate limiting: max 3 new memories per conversation turn

### AC-4: User Commands
- [ ] `/memory` — shows all stored memories for the user, grouped by category
- [ ] `/forget` — deletes ALL memories for the user, with confirmation prompt
- [ ] `/forget [topic]` — deletes memories related to a specific topic
- [ ] Commands respond within 2 seconds

### AC-5: Memory Quality
- [ ] Remember: topics studied, difficulty areas, learning preferences, exam dates, goals
- [ ] Forget: casual greetings, small talk, bot errors, duplicate facts
- [ ] Memory text is concise (under 100 chars per memory)
- [ ] Old memories decay: memories not recalled in 30 days get lower priority

---

## Memory Categories

| Category | Examples | Priority |
|----------|----------|----------|
| **Academic Profile** | "Studies Class 10 AI (subject code 417)" | Critical |
| **Topics Studied** | "Studied Neural Networks in Chapter 5" | High |
| **Difficulty Areas** | "Struggles with Python list comprehensions" | High |
| **Learning Style** | "Prefers examples over theory" | Medium |
| **Exam Context** | "Board exams in March 2026" | Medium |
| **Goals** | "Wants to score 95+ in AI" | Medium |
| **Content Preferences** | "Likes PDF notes over video explanations" | Low |

**DO NOT memorize:**
- Greetings ("hi", "hello", "thanks")
- Bot errors or retry attempts
- Exact message text (store extracted facts only)
- Sensitive personal information beyond academic context

---

## Mem0 Configuration

```python
MEM0_CONFIG = {
    "version": "v1.1",
    "embedder": {
        "provider": "google",
        "config": {
            "model": "models/gemini-embedding-001",
            "embedding_dims": 768,
        }
    },
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "dbname": "postgres",
            "collection_name": "student_memories",
            "embedding_model_dims": 768,
            "user": "<from-supabase>",
            "password": "<from-supabase>",
            "host": "<from-supabase>",
            "port": 5432,
        }
    },
}
```

---

## Implementation Plan

### Week 3: Core Memory Infrastructure

#### Day 1-2: MemoryService
**New file:** `telegram_bot/services/memory_service.py`

```python
class MemoryService:
    """Persistent student memory using Mem0 + Supabase pgvector."""

    async def recall(self, user_id: str, query: str, limit: int = 5) -> list[dict]:
        """Retrieve relevant memories for context injection."""

    async def capture(self, user_id: str, messages: list[dict]) -> list[str]:
        """Extract and store key facts from a conversation turn."""

    async def get_all(self, user_id: str) -> list[dict]:
        """Get all memories for /memory command."""

    async def forget_all(self, user_id: str) -> int:
        """Delete all memories for /forget command. Returns count deleted."""

    async def forget_topic(self, user_id: str, topic: str) -> int:
        """Delete memories matching a topic. Returns count deleted."""
```

#### Day 3: Integrate Recall into Agent
**File:** `telegram_bot/services/agent_service.py`

Before building the system prompt:
1. Call `memory_service.recall(user_id, user_message)`
2. Format memories into a prompt section
3. Inject into system prompt

#### Day 4-5: Integrate Capture into Agent
**File:** `telegram_bot/services/agent_service.py`

After receiving the AI response:
1. Call `memory_service.capture(user_id, [user_msg, bot_response])`
2. Fire-and-forget (don't block the response to the student)
3. Log new memories for debugging

### Week 4: Commands + Quality + Polish

#### Day 6: System Prompt Memory Section
**File:** `telegram_bot/prompts/agent_system.md`

Add:
```markdown
## What I Remember About You
{memories}

Use these memories to personalize your responses. Reference past topics naturally.
If a memory seems outdated or wrong, the student can use /forget to clear it.
```

#### Day 7-8: /memory and /forget Commands
**File:** `telegram_bot/handlers.py`

- `/memory` handler: calls `memory_service.get_all()`, formats as categorized list
- `/forget` handler: confirmation prompt ("Are you sure? This deletes all memories."), then calls `memory_service.forget_all()`
- `/forget Neural Networks` handler: calls `memory_service.forget_topic()`

#### Day 9: Memory Quality Tuning
- Test with real conversation samples from the 14,470 interaction logs
- Tune: what gets captured vs ignored
- Tune: deduplication threshold
- Tune: relevance cutoff for recall

#### Day 10: Integration Testing + Deploy
- End-to-end test: new user → onboarding → study session → restart → memories persist
- Load test: 50 concurrent users with memory recall
- Deploy to Cloud Run with `MEM0_ENABLED=true` feature flag

---

## Files to Modify

| File | Change |
|------|--------|
| `telegram_bot/services/agent_service.py` | Add memory recall before prompt, capture after response |
| `telegram_bot/prompts/agent_system.md` | Add memory section template |
| `telegram_bot/handlers.py` | Add /memory and /forget command handlers |
| `config/settings.py` | Add Mem0 config, Google AI API key, `MEM0_ENABLED` flag |
| `requirements.txt` | Add mem0ai, google-generativeai |

## New Files

| File | Purpose |
|------|---------|
| `telegram_bot/services/memory_service.py` | Mem0 wrapper with recall, capture, forget operations |

---

## Configuration

```python
# config/settings.py additions
GOOGLE_AI_API_KEY: str      # for gemini-embedding-001 (free)
MEM0_ENABLED: bool = False  # feature flag for gradual rollout
MEM0_RECALL_LIMIT: int = 5  # max memories injected per turn
MEM0_CAPTURE_LIMIT: int = 3 # max new memories per turn
```

---

## Cost Analysis

| Component | Cost | Notes |
|-----------|------|-------|
| gemini-embedding-001 | **Free** | 1,500 requests/min, free tier |
| Supabase pgvector | **Free** | Included in Supabase free tier (500MB) |
| Mem0 (self-hosted) | **Free** | Open source, self-managed |
| Storage (est. 50K memories) | ~10MB | Well within free tier |

**Total incremental cost: $0/month**

---

## Rollback Plan

1. Set `MEM0_ENABLED=false` in Cloud Run environment
2. Redeploy — bot works exactly as before, without memory
3. Memory data persists in Supabase (not deleted on disable)
4. Can re-enable anytime without data loss

---

## Testing

1. **Unit tests:** MemoryService with mock Mem0 client
2. **Integration tests:** Full flow with test Supabase project
3. **Recall quality:** Test with 20 real conversation samples — verify relevant memories are retrieved
4. **Capture quality:** Test with 20 real conversations — verify useful facts extracted, noise ignored
5. **Command tests:** /memory shows memories, /forget clears them, /forget [topic] is selective
6. **Degradation test:** Kill Mem0 connection → verify bot still works without memory
7. **Load test:** 50 concurrent users with memory operations → verify < 200ms recall latency
