# Phase 6: Advanced Features

**Timeline:** Week 11+
**Status:** Not Started
**Dependencies:** Phase 5 (Website Unification)

---

## User Stories

1. **As a student**, I want the bot to remind me to review topics I'm likely forgetting so I retain knowledge for board exams.
2. **As a student**, I want to see a knowledge map of what I know and what I don't so I can focus my study time effectively.
3. **As a student**, I want to use the bot on Discord and the website too so I can learn wherever I am.

---

## Feature 1: Spaced Repetition Engine

### Algorithm

Based on the **Ebbinghaus forgetting curve** and the **SM-2 (SuperMemo 2)** algorithm:

```
next_interval = previous_interval * ease_factor
ease_factor = max(1.3, EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
```

Where `quality` is derived from quiz performance (0-5 scale):
- 5: Perfect recall, no hesitation
- 4: Correct after brief hesitation
- 3: Correct with difficulty
- 2: Incorrect, but recognized correct answer
- 1: Incorrect, vaguely remembered
- 0: Complete blackout

### Data Model

```sql
CREATE TABLE review_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES bot_users(telegram_id),
    topic_id VARCHAR(100) NOT NULL,       -- e.g., "class10_ai_unit3_nlp"
    topic_name VARCHAR(255) NOT NULL,
    subject VARCHAR(10) NOT NULL,
    class VARCHAR(5) NOT NULL,

    -- SM-2 state
    ease_factor FLOAT DEFAULT 2.5,
    interval_days INT DEFAULT 1,
    repetition_count INT DEFAULT 0,
    last_quality INT,

    -- Scheduling
    last_reviewed_at TIMESTAMPTZ,
    next_review_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, topic_id)
);

CREATE INDEX idx_review_due ON review_schedule(user_id, next_review_at)
WHERE next_review_at <= NOW();
```

### How Topics Are Tracked

Topics enter the review schedule from three sources:
1. **Questions asked:** When a student asks about NLP, the topic "NLP" is added/updated
2. **Notes accessed:** When a student downloads Unit 3 notes, related topics are added
3. **Quiz performance:** Quiz results directly update SM-2 parameters

### Proactive Review Messages

A background job (Cloud Scheduler + Cloud Run job) runs daily at 8:00 AM IST:

1. Query `review_schedule` for entries where `next_review_at <= NOW()`
2. Group by user, limit to 3 topics per day (avoid spam)
3. Send Telegram message:

```
📚 Review Reminder!

Hey {name}! It's been {days} days since you studied these topics:

1. NLP Basics (AI, Unit 3) - last reviewed 7 days ago
2. Data Visualization (AI, Unit 5) - last reviewed 14 days ago

Quick review? Just ask me about any of these topics, or type /quiz nlp for a quick 5-question test!
```

4. If student ignores 3 consecutive reminders, reduce frequency to weekly
5. Respect quiet hours: no messages before 7 AM or after 10 PM IST

### Integration with Quiz Mode

When a student takes a quiz on a reviewed topic:
- Quiz score maps to SM-2 quality (0-5)
- Update `ease_factor` and `interval_days`
- Schedule next review
- If quality < 3, reset interval to 1 day (re-learn)

### Settings

Students control their reminders:
- `/reminders on` / `/reminders off` -- toggle
- `/reminders time 6pm` -- set preferred time
- `/reminders frequency daily|weekly` -- frequency

---

## Feature 2: Progress Tracking / Knowledge Graph

### Topic Taxonomy

A hierarchical topic structure derived from CBSE syllabus:

```
Class 10 AI (417)
├── Unit 1: Introduction to AI
│   ├── What is AI
│   ├── AI in daily life
│   ├── Domains of AI
│   └── AI project cycle
├── Unit 2: AI Project Cycle
│   ├── Problem scoping
│   ├── Data acquisition
│   ├── Data exploration
│   ├── Modelling
│   └── Evaluation
├── Unit 3: Data Sciences
│   ├── Data collection
│   ├── Data visualization
│   └── Data analysis
...
```

### Data Model

```sql
CREATE TABLE topic_taxonomy (
    topic_id VARCHAR(100) PRIMARY KEY,
    parent_id VARCHAR(100) REFERENCES topic_taxonomy(topic_id),
    name VARCHAR(255) NOT NULL,
    class VARCHAR(5) NOT NULL,
    subject VARCHAR(10) NOT NULL,
    unit INT,
    depth INT NOT NULL,  -- 0=subject, 1=unit, 2=topic, 3=subtopic
    cbse_weight FLOAT    -- approximate marks weightage in board exam
);

CREATE TABLE student_mastery (
    user_id BIGINT NOT NULL REFERENCES bot_users(telegram_id),
    topic_id VARCHAR(100) NOT NULL REFERENCES topic_taxonomy(topic_id),
    mastery_level FLOAT DEFAULT 0.0,  -- 0.0 to 1.0
    interactions INT DEFAULT 0,
    last_interaction_at TIMESTAMPTZ,
    confidence VARCHAR(10),  -- 'low', 'medium', 'high'
    PRIMARY KEY (user_id, topic_id)
);
```

### Mastery Calculation

Mastery level (0.0 - 1.0) is computed from weighted signals:

| Signal | Weight | Source |
|---|---|---|
| Questions asked on topic | 0.15 | Conversation history |
| Notes accessed for topic | 0.10 | Content access logs |
| Quiz score on topic | 0.40 | Quiz results |
| Spaced repetition quality | 0.25 | Review schedule |
| Time since last interaction | -0.10 | Decay factor |

Mastery decays over time if not reinforced (ties into spaced repetition).

### Knowledge Map Visualization

On the website dashboard, the knowledge map renders as:

1. **Tree view** (default): expandable tree showing units > topics with color-coded mastery
   - Green (>0.7): Mastered
   - Yellow (0.4-0.7): In Progress
   - Red (<0.4): Needs Work
   - Grey: Not Started

2. **Radar chart**: one axis per unit, radius = average mastery of that unit. Shows at-a-glance strengths and weaknesses.

3. **Heatmap calendar**: GitHub-style contribution grid showing study activity per day.

### API Endpoints

```
GET  /api/mastery/{user_id}                    -- full mastery data
GET  /api/mastery/{user_id}/radar              -- radar chart data
GET  /api/mastery/{user_id}/topics/{topic_id}  -- single topic detail
GET  /api/mastery/{user_id}/gaps               -- weakest topics (study recommendations)
POST /api/mastery/{user_id}/update             -- internal: called after interactions
```

---

## Feature 3: Multi-Platform Adapters

### Platform-Agnostic Message Contracts

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Platform(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEBSITE = "website"

@dataclass
class ChatMessage:
    platform: Platform
    user_id: str              # platform-specific user ID
    unified_user_id: int      # our internal user ID (telegram_id or linked)
    text: str
    reply_to_message_id: Optional[str] = None
    is_group: bool = False
    group_id: Optional[str] = None
    attachments: list = None  # file URLs, images, etc.

@dataclass
class ChatResponse:
    text: str
    parse_mode: Optional[str] = None  # 'markdown', 'html', None
    reply_to: Optional[str] = None
    attachments: list = None
    buttons: list = None      # platform-adapted inline buttons
```

### Adapter Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Telegram   │  │   Discord    │  │   Website    │
│   Adapter    │  │   Adapter    │  │   Adapter    │
│              │  │              │  │              │
│ python-      │  │ discord.py   │  │ WebSocket    │
│ telegram-bot │  │              │  │ (FastAPI)    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                │                 │
         ┌──────▼──────┐  ┌──────▼──────┐
         │  Message     │  │   User      │
         │  Gateway     │  │   Resolver  │
         │              │  │             │
         │  Normalizes  │  │  Maps       │
         │  to ChatMsg  │  │  platform   │
         │              │  │  ID to      │
         └──────┬───────┘  │  unified ID │
                │          └──────┬──────┘
                └────────┬────────┘
                         │
                  ┌──────▼──────┐
                  │   Agent     │
                  │   Service   │
                  │             │
                  │  (existing) │
                  │  LLM +      │
                  │  tools +    │
                  │  memory     │
                  └─────────────┘
```

### Telegram Adapter (Refactor)

Current `handlers.py` is tightly coupled to `python-telegram-bot`. Refactor into:

```
telegram_bot/
├── adapters/
│   ├── base.py              # Abstract PlatformAdapter
│   ├── telegram_adapter.py  # Telegram-specific: webhook, message parsing, reply formatting
│   ├── discord_adapter.py   # Discord-specific: bot events, message parsing
│   └── web_adapter.py       # WebSocket: connection management, message parsing
├── gateway.py               # Message Gateway: normalize -> route -> respond
├── user_resolver.py         # Platform ID -> unified user ID resolution
└── handlers.py              # Becomes thin: just registers Telegram handlers
```

### Discord Adapter

```python
# Key implementation details
import discord
from discord.ext import commands

class DiscordAdapter(PlatformAdapter):
    def __init__(self, gateway):
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        self.gateway = gateway

    async def on_message(self, message):
        if message.author.bot:
            return
        chat_msg = self.normalize(message)
        response = await self.gateway.process(chat_msg)
        await self.send_response(message.channel, response)

    def normalize(self, message) -> ChatMessage:
        return ChatMessage(
            platform=Platform.DISCORD,
            user_id=str(message.author.id),
            unified_user_id=self.resolve_user(message.author.id),
            text=message.content,
            is_group=not isinstance(message.channel, discord.DMChannel),
            group_id=str(message.guild.id) if message.guild else None,
        )
```

### Website Chat Widget (WebSocket)

```python
# FastAPI WebSocket endpoint
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    token = await websocket.receive_text()
    user = await verify_supabase_token(token)

    adapter = WebAdapter(gateway)
    try:
        while True:
            data = await websocket.receive_json()
            chat_msg = adapter.normalize(data, user)
            response = await gateway.process(chat_msg)
            await websocket.send_json(adapter.format_response(response))
    except WebSocketDisconnect:
        pass
```

### User Resolution

```python
class UserResolver:
    """Maps platform-specific IDs to unified user identity."""

    async def resolve(self, platform: Platform, platform_user_id: str) -> int:
        if platform == Platform.TELEGRAM:
            return int(platform_user_id)  # telegram_id IS our primary key

        if platform == Platform.DISCORD:
            row = await supabase.table("platform_links") \
                .select("telegram_id") \
                .eq("platform", "discord") \
                .eq("platform_user_id", platform_user_id) \
                .single()
            return row["telegram_id"]

        if platform == Platform.WEBSITE:
            row = await supabase.table("bot_users") \
                .select("telegram_id") \
                .eq("website_user_id", platform_user_id) \
                .single()
            return row["telegram_id"]
```

---

## Implementation Plan

### Spaced Repetition (Week 11-12)
1. Create `review_schedule` table
2. Build topic extraction from conversation/content access events
3. Implement SM-2 algorithm as a service
4. Build Cloud Scheduler job for daily reminders
5. Add `/reminders` command handlers
6. Integrate with quiz mode (Phase 4)
7. Test with 10 beta users, tune reminder frequency

### Knowledge Graph (Week 12-13)
8. Create `topic_taxonomy` table, populate from CBSE syllabus PDFs
9. Create `student_mastery` table
10. Build mastery calculation service
11. Build API endpoints for mastery data
12. Build website components: tree view, radar chart, heatmap
13. Connect mastery updates to conversation/quiz/content events
14. Test mastery accuracy against manual assessment of 5 students

### Multi-Platform (Week 13-15)
15. Define `ChatMessage` / `ChatResponse` dataclasses
16. Create `PlatformAdapter` abstract base class
17. Refactor `handlers.py` into `TelegramAdapter` + `MessageGateway`
18. Verify Telegram still works identically after refactor
19. Build `DiscordAdapter` with discord.py
20. Create `platform_links` table for cross-platform identity
21. Build WebSocket endpoint for website chat
22. Build chat widget component on academy platform
23. End-to-end test: same student on all 3 platforms, verify shared memory

---

## Data Model Summary

### New Tables

| Table | Purpose |
|---|---|
| `review_schedule` | SM-2 spaced repetition state per user per topic |
| `topic_taxonomy` | Hierarchical CBSE topic structure |
| `student_mastery` | Per-user mastery level per topic |
| `platform_links` | Maps Discord/other platform IDs to unified user |
| `reminder_preferences` | User settings for reminder timing/frequency |

### New Services

| Service | Purpose |
|---|---|
| `SpacedRepetitionService` | SM-2 calculations, scheduling |
| `MasteryService` | Mastery level computation, gap analysis |
| `ReminderService` | Proactive message sending, quiet hours |
| `MessageGateway` | Platform-agnostic message routing |
| `UserResolver` | Cross-platform identity resolution |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Reminder spam annoys students | Users mute/block bot | Cap at 3/day, respect opt-out, reduce on ignore |
| Mastery scores feel inaccurate | Students lose trust | Calibrate with manual assessment; show confidence level |
| Multi-platform refactor breaks Telegram | Service disruption for 2,870 users | Feature flag: run old and new handlers in parallel during migration |
| Discord moderation is harder than Telegram | Inappropriate content in groups | Reuse existing content moderator; add Discord-specific role permissions |
| WebSocket connections at scale | Server resource exhaustion | Connection limits per user, heartbeat timeout, Cloud Run autoscaling |

---

## Success Metrics

- 50%+ of reminded students engage with at least one review within 24 hours
- Knowledge map mastery scores correlate >0.7 with actual quiz performance
- Discord reaches 500 active users within 2 months of launch
- Website chat widget used by 20%+ of linked-account students
- Zero Telegram regression after multi-platform refactor
