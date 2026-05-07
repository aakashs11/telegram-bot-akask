# ASK AI - Development Skills and Tools Setup

Guide for installing and configuring development skills, plugins, and tooling for the ASK AI project.

---

## Recommended Skills Stack

### 1. feature-dev (Official Anthropic Plugin)

**What:** 7-phase guided feature development workflow — Discovery, Explore, Clarify, Design, Implement, Review, Summary. Forces structured thinking before writing code.

**When to use:** For any new feature that touches multiple files or services. Prevents the "just start coding" anti-pattern that leads to rework.

**Source:** `/Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/feature-dev/`

**Install:**
```bash
cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/feature-dev/ .cursor/skills/feature-dev/
```

Or use the plugin installer:
```
/plugin install feature-dev@claude-plugin-directory
```

**Usage examples:**
- Phase 1 database migration: Run Discovery to map all Google Sheets dependencies before writing migration code
- Phase 3 RAG pipeline: Run Design phase to define chunking strategy before implementation

---

### 2. GSD — Get Shit Done

**What:** Spec-driven development with context engineering for complex features. Builds a project context file that prevents quality degradation in long coding sessions. Forces spec writing, implementation planning, and structured execution.

**When to use:** For complex multi-service features like the RAG pipeline, memory integration, or Supabase migration. Especially valuable when a feature spans multiple sessions.

**Source:** https://github.com/gsd-build/get-shit-done

**Install:**
```bash
npx get-shit-done-cc --cursor --local
```

**Key commands:**
| Command | Purpose |
|---|---|
| `/gsd:map-codebase` | Analyze codebase and generate context map |
| `/gsd:new-project` | Start a new feature project with spec |
| `/gsd:quick` | Quick task within existing project |
| `/gsd:execute-phase` | Execute a specific phase of the spec |

**Usage examples:**
- Before Phase 2 (Memory): `/gsd:new-project` to spec out the Mem0 integration
- During implementation: `/gsd:execute-phase` to work through each part systematically
- Context retention: The generated project file preserves decisions across sessions

---

### 3. pm-skills (Product Management)

**What:** 65 PM skills and 36 workflows covering PRDs, sprint planning, user personas, OKRs, competitive analysis, and more. Brings product management discipline to solo development.

**When to use:** Before starting any phase, write a PRD. Use sprint planning for weekly goals. Create user personas to validate feature decisions against real student needs.

**Source:** https://github.com/phuryn/pm-skills

**Install:**
```bash
git clone https://github.com/phuryn/pm-skills.git /tmp/pm-skills
cp -r /tmp/pm-skills/skills/ .cursor/skills/pm-skills/
```

**Key commands:**
| Command | Purpose |
|---|---|
| `/write-prd` | Generate a Product Requirements Document |
| `/sprint` | Plan a development sprint |
| `/discover` | Run a discovery process for a feature |
| `/plan-okrs` | Define Objectives and Key Results |

**Usage examples:**
- Phase 0 kickoff: `/write-prd` for the quick fixes phase to define scope and success criteria
- Weekly planning: `/sprint` to set realistic weekly goals across phases
- Feature validation: `/discover` to validate Phase 4 features (quiz, study planner) against student data

---

### 4. claude-code-setup

**What:** Analyzes the codebase and recommends optimal configuration — hooks, skills, MCP servers, subagent patterns, and project-specific settings.

**When to use:** Run once at the start of the project to get a baseline configuration. Re-run after major architectural changes (e.g., after Phase 1 migration).

**Source:** `/Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/claude-code-setup/`

**Install:**
```bash
cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/claude-code-setup/ .cursor/skills/claude-code-setup/
```

**Usage:** Run the setup analysis and review recommendations. Not all suggestions will be relevant — pick what fits the project's needs.

---

### 5. supabase (External Plugin)

**What:** Database operations, authentication, storage, and realtime capabilities via MCP. Enables direct database interaction from the editor — schema design, migrations, queries, and RLS policy management.

**When to use:** During Phase 1 (database migration) and all subsequent phases. Essential for schema design, writing migrations, testing queries, and managing RLS policies.

**Source:** `/Users/aakash/Desktop/Repos/skills/claude-plugins-official/external_plugins/supabase/`

**Install:**
```bash
cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/external_plugins/supabase/ .cursor/skills/supabase/
```

Or use the plugin installer:
```
/plugin install supabase@claude-plugin-directory
```

**Usage examples:**
- Phase 1: Design schema, write migrations, set up RLS policies
- Phase 2: Create memory tables with pgvector columns
- Phase 3: Create content chunk tables with vector indexes

---

### 6. security-guidance

**What:** A hook that monitors edits and warns about security-sensitive patterns — SQL injection, XSS, hardcoded secrets, insecure API patterns, and more.

**When to use:** Always on. Runs as a background hook that flags issues as you code. Particularly important when handling student data and API keys.

**Source:** `/Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/security-guidance/`

**Install:**
```bash
cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/security-guidance/ .cursor/skills/security-guidance/
```

**Relevant scenarios:**
- Database queries with user input (SQL injection prevention)
- Telegram webhook handling (input validation)
- API key management (Secret Manager integration)
- Student data handling (privacy, RLS policies)

---

### 7. playground

**What:** Creates interactive HTML playgrounds with live preview. Generates self-contained HTML files that can be opened in a browser for visual debugging and prototyping.

**When to use:** For creating interactive demos, concept maps, student-facing content explorers, or visual debugging of data flows.

**Source:** `/Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/playground/`

**Install:**
```bash
cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/plugins/playground/ .cursor/skills/playground/
```

**Usage examples:**
- Visualize the RAG pipeline (document flow from Drive to chunks to vectors)
- Create interactive content browser for testing note retrieval
- Debug memory retrieval by visualizing memory graph

---

## Linear Setup (Issue Tracking)

Linear is free for small teams and integrates with Cursor via MCP plugin.

### Setup Steps

1. **Create account:** Go to https://linear.app and sign up (free tier)

2. **Create workspace:** Name it "LearnWithAakash" or "ASK AI"

3. **Create project:** "ASK AI Platform"

4. **Create labels:**
   - `phase-0`, `phase-1`, `phase-2`, `phase-3`, `phase-4`, `phase-5`, `phase-6`
   - `bug`, `enhancement`, `tech-debt`, `documentation`
   - `priority-p0`, `priority-p1`, `priority-p2`, `priority-p3`

5. **Create cycles (epics):**

   | Cycle | Name | Target |
   |---|---|---|
   | Phase 0 | Quick Fixes | Week 1 |
   | Phase 1 | Supabase Migration | Weeks 2-3 |
   | Phase 2 | Memory Layer | Weeks 3-4 |
   | Phase 3 | Content RAG | Weeks 4-6 |
   | Phase 4 | Smart Features | Weeks 6-8 |
   | Phase 5 | Website Unification | Weeks 8-10 |
   | Phase 6 | Advanced Features | Weeks 10+ |

6. **Install Linear plugin for Cursor:**

   ```bash
   cp -r /Users/aakash/Desktop/Repos/skills/claude-plugins-official/external_plugins/linear/ .cursor/skills/linear/
   ```

7. **Usage:** Once connected, issues can be created, updated, and tracked directly from Cursor. Use the Linear MCP to sync between code changes and issue status.

---

## Additional Useful Skills (Optional)

These are not required but can add value for specific workflows.

### spec-driven-dev
- **What:** Deep spec interviews for complex features. Asks probing questions before generating implementation plans.
- **Source:** DaanFerdinandusse/AI-agent-plugins
- **When:** For features where requirements are ambiguous (e.g., "make the bot smarter")

### claude-code-templates
- **What:** Templates for PostgreSQL MCP, test generation, CI/CD pipelines, and more.
- **Source:** davila7/claude-code-templates
- **When:** During Phase 1 for PostgreSQL migration patterns and test scaffolding

### learn-faster-kit
- **What:** Educational framework with spaced repetition, active recall, and learning analytics.
- **Source:** Awesome Claude Code list
- **When:** Phase 4 (smart features) for implementing spaced repetition and study planning

### compound-engineering
- **What:** Turns past mistakes into lessons. Maintains a "lessons learned" database that feeds into future decisions.
- **Source:** EveryInc
- **When:** After each phase retrospective to capture what worked and what didn't

---

## Quick Start Checklist

For getting the development environment ready:

- [ ] Install feature-dev skill
- [ ] Install GSD and run `/gsd:map-codebase`
- [ ] Install security-guidance hook
- [ ] Install supabase plugin
- [ ] Set up Linear workspace and install plugin
- [ ] Run claude-code-setup for baseline recommendations
- [ ] Install pm-skills and write initial PRD for Phase 0
- [ ] Install playground for visual debugging
