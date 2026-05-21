# Handoff message (copy-paste)

Send this to a new developer after granting GitHub access and creating a read-only Bitwarden machine account token.

---

Hi — here’s everything to get started on the Telegram bot **platformization** work.

**Repo:** https://github.com/aakashs11/telegram-bot-akask  
**Branch to use:** `codex/platformization` (not `main`)  
**Guide (read this first):** `docs/ONBOARDING.md` on that branch — setup, credentials, testing, and how to open PRs.

**Quick setup:**
1. Clone the repo and checkout `codex/platformization`
2. Install Python 3.12, pipenv, ngrok, and the Bitwarden CLI (`bws`) — steps are in the onboarding doc
3. I’ll send you a **Bitwarden access token** (and passcode if via Send) separately — use it with project ID `33403fe4-c585-4a77-ace7-b4510082ad50` and run `./scripts/export_dev_env_from_bws.sh` to create `.env` and `service_account.json`
4. Run `pipenv install`, then `./start_devtest.sh`
5. Test the dev bot on Telegram: **@akask_dev_bot**

**Your workflow:** branch off `codex/platformization` (e.g. `feat/platformization/your-feature`), open PRs **into** `codex/platformization`. Run `pipenv run python -m evals.chat_runtime_eval` before pushing. Don’t commit secrets or merge to `main` yourself.

**Coordination:** only one of us should run `start_devtest.sh` at a time (webhook points to whoever’s ngrok is last). Ping me before you start local testing.

If anything breaks, check the troubleshooting section in `docs/ONBOARDING.md` or message me.

---

*Maintainer: replace the Bitwarden token delivery line if you use Bitwarden Send vs a raw machine account token.*
