# Developer onboarding — platformization

Single guide for getting the repo running, pulling dev credentials, and opening pull requests against the **platformization** workstream.

**Maintainer provides separately (not in git):**

- Bitwarden access token (read-only) + Send passcode, if applicable  
- Dev Telegram bot **[@akask_dev_bot](https://t.me/akask_dev_bot)**  
- GitHub collaborator access to `aakashs11/telegram-bot-akask`

Copy-paste invite text for new developers: [`docs/HANDOFF_MESSAGE.md`](HANDOFF_MESSAGE.md)

---

## 1. What you are working on

**Platformization** separates *platform-specific* code (Telegram, future Discord/web) from *shared* bot logic.

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Contracts | `telegram_bot/runtime/contracts.py` | `ChatMessage`, `ChatResponse`, `Platform`, `ChatType` |
| Runtime | `telegram_bot/runtime/chat_runtime.py` | Routing, moderation gates, agent calls (platform-neutral) |
| Adapter | `telegram_bot/adapters/telegram_adapter.py` | Map Telegram `Update` → `ChatMessage`, send replies |
| Evals | `evals/chat_runtime_eval.py` | Offline routing tests (no Telegram/OpenAI required for most cases) |

Architecture decision: **ADR-009** in `DECISIONS.md` (adapter pattern, reuse “brain” across platforms).

**Integration branch:** `codex/platformization`  
**Do not branch from `main` for this work** until platformization has been merged upstream.

---

## 2. One-time machine setup

Install these before cloning:

| Tool | Version | Install |
|------|---------|---------|
| Git | any recent | [git-scm.com](https://git-scm.com/) |
| Python | **3.12** | [python.org](https://www.python.org/downloads/) |
| pipenv | latest | `pip install pipenv` |
| ngrok | account required | [ngrok.com/download](https://ngrok.com/download) — sign up, then `ngrok config add-authtoken <token>` |
| Bitwarden CLI (`bws`) | 2.x | `curl -fsSL https://bws.bitwarden.com/install \| sh` then `export PATH="$PATH:$HOME/.local/bin"` |

Optional: [GitHub CLI](https://cli.github.com/) (`gh`) for creating PRs from the terminal.

---

## 3. Clone and checkout platformization

```bash
git clone https://github.com/aakashs11/telegram-bot-akask.git
cd telegram-bot-akask

git fetch origin
git checkout codex/platformization
git pull origin codex/platformization
```

Confirm you are on the right branch:

```bash
git branch --show-current
# Expected: codex/platformization
```

Install Python dependencies:

```bash
pipenv install
```

---

## 4. Dev credentials (Bitwarden, one-time)

The bot needs `.env` and `service_account.json` in the **repository root**. They are gitignored.

### 4.1 Values you will receive

From the maintainer (e.g. Bitwarden Send + passcode, or a read-only machine account token):

- `BWS_ACCESS_TOKEN` — Secrets Manager machine account token  
- `BWS_PROJECT_ID` — `33403fe4-c585-4a77-ace7-b4510082ad50` (project: `telegram-bot-akask-dev`)

### 4.2 Export to local files

```bash
cd telegram-bot-akask   # project root

export BWS_ACCESS_TOKEN='<token-from-maintainer>'
export BWS_PROJECT_ID='33403fe4-c585-4a77-ace7-b4510082ad50'

./scripts/export_dev_env_from_bws.sh
```

This writes:

- `.env` — `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `YOUTUBE_API_KEY`, `SHEET_ID`, `DRIVE_FOLDER_ID`  
- `service_account.json` — decoded from `SERVICE_ACCOUNT_JSON_B64`

Lock down permissions:

```bash
chmod 600 .env service_account.json
```

**After this step you do not need `bws` to run the bot daily.**

### 4.3 Required variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | **Development** bot only |
| `OPENAI_API_KEY` | Agent + moderation |
| `YOUTUBE_API_KEY` | Video search tool |
| `SHEET_ID` | Profiles + moderation sheet (must be `SHEET_ID`, not `GOOGLE_SHEET_ID`) |
| `DRIVE_FOLDER_ID` | Notes / Drive root |

More detail: `docs/SECRETS.md` (credentials only; this doc supersedes it for workflow).

### 4.4 What you are not given

- Production bot token or Cloud Run deploy access  
- GCP Secret Manager write access  
- Merging to `main` or running `./deploy.sh` (maintainer only)

`service_account.json` is for **local Google APIs** (Sheets/Drive), not “production server” access.

---

## 5. Run the dev bot locally

Coordinate with the maintainer: **only one person** should run the dev webhook at a time (last `start_devtest.sh` wins).

```bash
./start_devtest.sh
```

The script starts uvicorn on port **8080**, opens ngrok, sets the Telegram webhook, and tails logs.

Useful log tail (separate terminal):

```bash
tail -f /tmp/telegram-bot-server.log
```

Message the development bot on Telegram: **[@akask_dev_bot](https://t.me/akask_dev_bot)**.

### 5.1 Quick verification

**Routing (no API cost):**

```bash
pipenv run python -m evals.chat_runtime_eval
```

**Full stack (OpenAI cost):**

```bash
pipenv run python -m evals.moderation_eval --verbose
```

**Imports:**

```bash
pipenv run python -c "from telegram_bot.runtime import ChatRuntime; print('ok')"
```

---

## 6. Git workflow and pull requests

### 6.1 Branching model

```text
main
 └── codex/platformization          ← integration branch (platformization)
      └── feat/platformization/…   ← your short-lived branches
```

| Rule | Detail |
|------|--------|
| Base branch | Always branch **from** `codex/platformization` |
| PR target | Open PRs **into** `codex/platformization` |
| Scope | One logical change per PR (adapter, runtime rule, eval cases, refactor) |
| Avoid | Long-lived forks; committing `.env`, `service_account.json`, or API keys |

### 6.2 Start a feature branch

```bash
git checkout codex/platformization
git pull origin codex/platformization

git checkout -b feat/platformization/<short-description>
# Examples:
#   feat/platformization/discord-adapter-skeleton
#   feat/platformization/runtime-reply-metadata
#   fix/platformization/group-mention-routing
```

### 6.3 Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new behavior  
- `fix:` — bug fix  
- `refactor:` — no behavior change  
- `test:` — evals / tests only  
- `docs:` — documentation only  

Example: `feat: add Discord adapter skeleton implementing ChatMessage mapping`

### 6.4 Before you push (checklist)

```bash
# On your feature branch
git status
git diff codex/platformization...HEAD --stat

# No secrets in diff
git diff codex/platformization...HEAD | grep -iE 'sk-proj|AAG[a-zA-Z0-9_-]{30,}|AIza' \
  && echo '⚠️ possible secret in diff' || echo '✅ no obvious API keys in diff'

# Platformization eval (preferred for your changes)
pipenv run python -m evals.chat_runtime_eval

# If you touched moderation or Telegram paths
pipenv run python -m evals.moderation_eval --verbose   # optional; uses OpenAI

# Imports
pipenv run python -c "from telegram_bot.application import application; print('✅ imports ok')"
```

If you add dependencies:

```bash
pipenv install <package>
pipenv requirements > requirements.txt
git add Pipfile requirements.txt
```

### 6.5 Push and open a PR

```bash
git add <files>    # prefer explicit paths over blind 'git add .'
git commit -m "feat: describe the change"
git push -u origin feat/platformization/<short-description>
```

**On GitHub:**

1. Open https://github.com/aakashs11/telegram-bot-akask  
2. **Compare & pull request**  
3. **Base:** `codex/platformization` ← **Compare:** your branch  
4. Fill in the template below  
5. Request review from maintainer — **do not merge** unless asked  

**With GitHub CLI:**

```bash
gh pr create \
  --base codex/platformization \
  --head feat/platformization/<short-description> \
  --title "feat: short title" \
  --body "$(cat <<'EOF'
## Summary
- What changed and why (platformization context)

## Test plan
- [ ] `pipenv run python -m evals.chat_runtime_eval`
- [ ] `./start_devtest.sh` — manual Telegram check (if adapter/handlers changed)
- [ ] Other: …

## Notes
- Breaking changes / follow-ups
EOF
)"
```

### 6.6 After review

```bash
# Stay up to date with integration branch
git checkout codex/platformization
git pull origin codex/platformization
git checkout feat/platformization/<short-description>
git merge codex/platformization   # or: git rebase codex/platformization
# resolve conflicts, re-run evals, push
```

Maintainer merges your PR into `codex/platformization`. Merging platformization → `main` is a separate release step.

---

## 7. Where to change code (platformization)

| Task | Start here |
|------|------------|
| New platform (e.g. Discord) | New file under `telegram_bot/adapters/`, implement mapping to `ChatMessage` / `ChatResponse` |
| Routing / moderation / agent path | `telegram_bot/runtime/chat_runtime.py` |
| Message shape / enums | `telegram_bot/runtime/contracts.py` |
| Telegram-only delivery | `telegram_bot/adapters/telegram_adapter.py`, `telegram_bot/handlers.py` |
| New routing scenarios | `evals/chat_runtime_cases.jsonl` + run `evals/chat_runtime_eval.py` |
| Prompts | `telegram_bot/prompts/*.md` |

---

## 8. Coordination and etiquette

1. **Webhook** — Tell the team before running `start_devtest.sh`; stop with Ctrl+C when done.  
2. **Costs** — `moderation_eval` and live bot traffic use OpenAI quota.  
3. **Secrets** — Never paste tokens in PRs, issues, or chat.  
4. **Admin bypass** — `ADMIN_USER_IDS` in `config/settings.py` is maintainer-controlled; ask if you need moderation bypass for testing.  
5. **Questions** — Prefer small PRs early over large silent branches.

---

## 9. Troubleshooting

| Problem | What to try |
|---------|-------------|
| `TELEGRAM_BOT_TOKEN is not set` | Re-run `export_dev_env_from_bws.sh`; confirm `.env` exists |
| Google Sheet / Drive errors | Confirm `service_account.json` present; maintainer shared Sheet/Drive with SA email |
| Bot silent in groups | Bot needs admin + delete rights; mention `@dev_bot_username` |
| `bws`: decryption key error | Token is placeholder or wrong — use maintainer’s real machine account token |
| Wrong branch in PR | Base must be `codex/platformization`, not `main` |
| Import errors | `pipenv install` on `codex/platformization` |

---

## 10. Further reading (optional)

| Document | When to use |
|----------|-------------|
| `docs/SECRETS.md` | Credential formats and maintainer upload notes |
| `QUICKSTART.md` | Extra Telegram/ngrok context |
| `DEVELOPMENT_WORKFLOW.md` | Production deploy and `main` release flow (not your default path) |
| `DECISIONS.md` | ADR-009 and architecture history |
| `README.md` | Product features and project layout |
| `.cursor/plans/07-phase-6-advanced.md` | Longer multi-platform design notes |

---

## Quick reference card

```bash
# Setup (once)
git clone https://github.com/aakashs11/telegram-bot-akask.git && cd telegram-bot-akask
git checkout codex/platformization && pipenv install
export BWS_ACCESS_TOKEN='…' BWS_PROJECT_ID='33403fe4-c585-4a77-ace7-b4510082ad50'
./scripts/export_dev_env_from_bws.sh && chmod 600 .env service_account.json

# Daily dev
git checkout codex/platformization && git pull
git checkout -b feat/platformization/my-change
./start_devtest.sh
pipenv run python -m evals.chat_runtime_eval

# PR
git push -u origin feat/platformization/my-change
# Open PR → base: codex/platformization
```
