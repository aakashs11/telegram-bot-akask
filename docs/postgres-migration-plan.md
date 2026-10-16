# Postgres migration plan

Living plan for moving the Telegram bot off Google Sheets and onto PostgreSQL, first on this PC and later on Supabase in Mumbai. Edit this file as decisions change. What already happened, and what each piece means, is in `docs/study-notes.md`.

The operational commands for the interaction log (backfill, reconciliation, backup, cutover) stay in `docs/INTERACTION_LOGGING.md`. This file is the plan for the whole database. That runbook is the procedure for the log table only.

## Where this stands

Updated 16 Oct 2026. Branch `feat/platformization/supabase-migration`. The Mac commit `2dfac84` (26 Sep 2026, ENG-79) added the interaction-log path. On this PC the dev bot still reads the local Docker database when `BOT_DATA_STORE=postgres`. The Mumbai Supabase project is at revision `20261013_0006` with 1,900 profiles, 222 files, 93 folders, and 163 warnings. Old logs are not in it. The next step is the Owner invite, then the Cloud Run secret. Production stays on Sheets.

| Piece | State |
| --- | --- |
| Branch | `feat/platformization/supabase-migration`, based on `codex/platformization` |
| Mac commit `2dfac84` | Committed and pushed. Interaction log only. Default mode remains `sheet` |
| Local Postgres | Running for this project on `127.0.0.1:5433`, database `ask_ai`. The PC's own Postgres 18 stays on port 5432 and is not this database |
| `interaction_events` | Created by Alembic revision `20260922_0001`. The dev bot has inserted live rows |
| Profiles, notes catalog, folders | Copied. The dev bot reads them when `BOT_DATA_STORE=postgres` |
| `warnings` | 163 rows imported on 13 Oct 2026. 14 extra sheet rows for one student were collapsed to the highest count. The dev bot is wired to this table. A private notes reply did not read it |
| Videos | YouTube, through `search_videos`. No Sheet and no Postgres table |
| `students` | 1,898 rows imported on 13 Oct 2026. 2 sheet rows rejected (`Computer Vision`, `Banking`) |
| `content_items` | 222 rows after the Drive sync on 13 Oct 2026 |
| `folders` | 93 rows after the Drive sync on 13 Oct 2026 |
| `BOT_DATA_STORE` | Default `sheet`. Dev `.env` is `postgres`. That reads `students`, `content_items`, `folders`, and `warnings`. Drive sync can replace the catalog tables and leave the sheets alone. The scheduled job does not run in this dev install because the job queue extra is not installed |
| Alembic on this PC | `20261013_0006` |
| Supabase project | Not created. No production `database-url` secret |
| Production | Unchanged. Do not deploy this branch yet |

## Goal

One PostgreSQL database holds the bot's own data: interaction logs, student profiles, the content catalog, folder mappings, and later moderation warnings. PDF files stay in Google Drive. Video search stays on YouTube. Content search stays on Gemini File Search. Student memory, when it is added, uses `pgvector` in this same database for Mem0 only.

Local Postgres is where the schema and the test cases are proved. Supabase Mumbai is the same engine with a different URL, a connection pooler, TLS, and backups. Merging to `main` ships the code. It does not point Cloud Run at the local database.

## Current decisions

| Decision | Choice | Change later if |
| --- | --- | --- |
| Database engine | PostgreSQL. Local Docker now, Supabase in Mumbai for production | |
| How the app connects | `DATABASE_URL` only. SQLAlchemy async, asyncpg, Alembic. No `supabase-py` in the bot | A hosted feature requires the Supabase client |
| First table | `interaction_events`, append-only, one row per private reply | |
| Log mode | `INTERACTION_LOG_MODE`: `sheet` (default), `dual`, `postgres`, `off` | |
| Log failures | Fail-open. A database error must not block the student reply. Write timeout 5 seconds | Logs become a no-loss ledger, in which case add a queue |
| Identity of a log row | One `event_id` generated in the handler. Postgres ignores a duplicate | |
| Student row | One row per Telegram user id. Class 10–12. Subject AI, CS, IT, or IP. Empty means not chosen | Discord or the website need accounts with no Telegram id |
| Content files | Catalog rows in Postgres. File bytes stay in Drive | |
| Videos | YouTube API. Not a table | |
| Content RAG | Gemini File Search. Not an embeddings column on the catalog | That decision is superseded |
| Memory vectors | `pgvector` later, for Mem0 only. Local image is `pgvector/pgvector:pg16` so the extension can be enabled without a new server | |
| Historical Sheet timestamps | Keep the raw text. Do not convert until a known interaction confirms the timezone. `Asia/Kolkata` is only an example | |
| Production cutover | Dual-write 3–7 days, payload reconciliation, restore drill, then `postgres` mode. Sheets rollback stays at least 72 hours | |
| Supabase plan | Free, with a weekly `pg_dump` stored off the project. ADR-020 | |
| Pool | Runtime uses the pooled URL. Alembic uses the direct URL. Locally one URL does both | |

ADR-011, ADR-012, and ADR-013 in `DECISIONS.md` record the engine, the log backfill, and the `students` key.

## What the Mac commit includes

Commit `2dfac84`, 26 Sep 2026, message `feat: add PostgreSQL interaction migration foundation (ENG-79)`.

- Alembic, revision `20260922_0001`, table `interaction_events`.
- Async engine, Postgres repository, Sheets repository, and `InteractionLoggingService`.
- Startup wiring in `main.py`. Private replies log from `telegram_bot/handlers.py`.
- Modes `sheet`, `dual`, `postgres`, and `off`. Default `sheet`.
- Backfill and reconciliation scripts. They read a frozen Sheet export. They do not run themselves.
- Tests. On the Mac, 21 passed and 6 Postgres tests were skipped because no database URL was set and Docker was down.
- Runbook `docs/INTERACTION_LOGGING.md`.
- `deploy.sh` uses `--update-env-vars` so a deploy does not wipe `INTERACTION_LOG_MODE`.

The commit does not create a Supabase project, does not copy old Sheet rows, and does not move profiles, notes, folders, or warnings.

## What this PC has proved

- A disposable Postgres on port 5433 accepts the log migration.
- With `INTERACTION_LOG_MODE=postgres` and `BOT_DATA_STORE=postgres`, a real private message reads `students`, `content_items`, and `folders`, and writes `interaction_events`.
- On 14 Oct 2026 the dev bot, for user `8405510906`, returned Class 12 AI notes, 8 videos, saved a profile change to class 11 subject IT and then to AI, and returned the Class 11 AI sample-paper folder. Each log insert succeeded in about 6 milliseconds. Class 11 IT sample papers are absent from the catalog, and those three replies said so.
- On 14 Oct 2026 `scripts/backup_postgres.py --restore-drill` wrote `artifacts/ask-ai-20261014T202956Z.dump` (76,538 bytes) and loaded it into a temporary database. The check matched revision `20261013_0006`, 1,898 students, 222 files, 93 folders, 163 warnings, and 22 log rows. That temporary database was dropped. `ask_ai` was not changed. The dump uses the Docker container’s `pg_dump`, because the Postgres tools on this PC are newer than Postgres 16 and a host dump does not restore into this database.
- On 16 Oct 2026 the Mumbai Free project was migrated to `20261013_0006`. This PC has no IPv6 route, and the direct host is IPv6-only, so Alembic and the dump used the session pooler on port 5432. The port 6543 pooler is still the one for Cloud Run. `students` has 1,900 rows. `Computer Vision` and `Banking` stayed rejected. `warnings` has 163 rows. Drive sync wrote 222 files and 93 folders. Old `Logs` were not copied, so `interaction_events` is empty. The public-schema dump `artifacts/ask-ai-20261016T180623Z.dump` (78,189 bytes) restored into a temporary Postgres 17 database with those same counts. The Supabase project was not given a second database.

`screener_output` and `entities_output` on those new rows are empty. `intent_output` is `agent`. The current agent does not fill screener or entities. Historical `Logs` rows are not copied. ADR-019.

## What waits

- Invite your brother as an Owner. The database password is already in `supabase.env` on this PC. Do not send it in chat.
- Store the port 6543 pooler URL in Secret Manager as `database-url` only when Cloud Run should connect. The dev bot stays on local Docker until then.
- Smoke-test one private message in dual-log mode against Supabase.
- Merge to `main` with production still on Sheets.
- Dual-write new logs for 3–4 days, then schedule the five-minute Drive sync.

## Architecture

```text
Telegram
  -> ChatRuntime
       -> UserService          students                         (sheet when the flag is sheet)
       -> agent tools
            get_notes           content_items + folders + Drive
            search_videos       YouTube                        (stays YouTube)
       -> group moderation      warnings                       (after 20261013_0006)
       -> InteractionLoggingService
            mode=postgres       local Postgres :5433 ask_ai.interaction_events
            mode=sheet          Google Sheet Logs              (production default today)
            mode=dual           both, same event_id
```

```mermaid
flowchart LR
  student["Student message"] --> runtime["ChatRuntime"]
  runtime --> pgTables["students, content_items, folders, warnings"]
  runtime --> youtube["YouTube"]
  runtime --> drive["Google Drive files"]
  runtime --> logs["interaction_events"]
  pgTables --> pg["PostgreSQL"]
  logs --> pg
```

On Supabase the box labeled PostgreSQL moves to Mumbai. The arrows stay the same. Cloud Run in `asia-south1` uses the pooled URL. Alembic, backfill, and `pg_dump` use the direct URL from an operator shell.

## Tables

| Table | Sheet it replaces | Status | One row is |
| --- | --- | --- | --- |
| `interaction_events` | `Logs` | Live locally. Old rows are not backfilled | One private reply. Never updated |
| `students` | `UserProfiles` | 1,898 rows. Bot reads it when the flag is `postgres` | One Telegram user. Updated when class or subject changes |
| `content_items` | `Index`, then replaced from Drive | 222 rows. Bot reads it when the flag is `postgres` | One Drive file: title, link, level, subject, type, topic, file id |
| `folders` | `Folders`, then replaced from Drive | 93 rows. Bot reads it when the flag is `postgres` | One Drive folder path |
| `warnings` | `Warnings` | 163 rows. Bot reads it when the flag is `postgres` | One user in one chat: count, last reason, banned |

`students` columns: `telegram_user_id` primary key, `username`, `current_class` (`10`, `11`, `12`, or NULL), `preferred_subject` (`AI`, `CS`, `IT`, `IP`, or NULL), `created_at`, `last_updated`, `class_updated_year`. NULL means the student has not chosen. The checks reject any other class or subject.

Log columns that are easy to misread:

| Column | On a new dev-bot row | On a future imported Sheet row |
| --- | --- | --- |
| `screener_output` | Empty. Moderation does not write this column | Whatever the old sheet stored |
| `intent_output` | `agent` | The old classifier's label |
| `entities_output` | Empty | The old classifier's class, subject, or topic text |
| `source_ref` | Empty | `sheet:<sheet-id>:row:<row-number>` |

## Local database

The project database is a Docker container named `ask-ai-postgres`, image `pgvector/pgvector:pg16`, published only on `127.0.0.1:5433`. User `bot`, database `ask_ai`. The password is the local practice password in `.env` and is not written here.

Port 5432 is the PC's system Postgres 18. This project does not use it.

```bash
docker start ask-ai-postgres
docker exec ask-ai-postgres pg_isready -U bot -d ask_ai
```

`docker rm -f ask-ai-postgres` deletes the container and the rows. After that, create it again and run `alembic upgrade head`.

Alembic's bookmark is one row in `alembic_version`. The local database is at `20261013_0004`. After the folders migration, head is `20261013_0005`.

## Implementation phases

Do these in order. Stop after each phase and confirm the check before starting the next.

### Phase 1 — Interaction log foundation

Done on the Mac, 26 Sep 2026, commit `2dfac84`.

The code can log to Sheets, Postgres, both, or neither. Schema, repositories, tests, backfill, reconciliation, and the runbook are in that commit. No live database was used. The handoff in `.planning/phases/01-supabase-migration/.continue-here.md` still says the work was uncommitted. That sentence is stale. The commit exists.

### Phase 2 — Local Postgres and a live log row

Done on this PC, 3 Oct 2026.

1. Done. Container `ask-ai-postgres` on port 5433.
2. Done. `alembic upgrade head` applied `20260922_0001`.
3. Done. `INTERACTION_LOG_MODE=postgres` in `.env`. The dev bot fetched a profile and notes from Sheets and wrote the reply to `interaction_events`.
4. Done, as a local-dev fix. `start_devtest.sh` no longer kills whatever is listening on port 8080. Odysseus SearXNG uses `127.0.0.1:8080`. The script moves to 8081, 8082, 8888, or 8090 when 8080 is taken.

Check that still works:

```bash
psql "postgresql://bot@127.0.0.1:5433/ask_ai" \
  -c "SELECT event_id, telegram_user_id, left(user_message, 80), intent_output, occurred_at FROM interaction_events ORDER BY created_at DESC LIMIT 5;"
```

### Phase 3 — `students` table

Started 3 Oct 2026. Confirmed in the local database on 13 Oct 2026. `\d students` shows the seven columns, `pk_students`, and both checks.

A first apply of `20261003_0002` also created `students_telegram_user_id_seq`, because a single integer primary key is treated as an identity column unless autoincrement is turned off. Telegram already assigned these ids. `20261013_0003` drops that default.

1. Done. Applied `migrations/versions/20261003_0002_create_students.py`.
2. Done on 13 Oct 2026. `alembic current` was `20261013_0003`. `\d students` shows an empty Default on `telegram_user_id`. With `BOT_DATA_STORE=postgres`, profile reads and writes go to this table.
3. Done on 13 Oct 2026. Dry-run: `scanned` 1900, `valid` 1898, `rejected` 2. Row 216 has subject `Computer Vision`. Row 306 has subject `Banking`. `--apply` imported 1,898 rows. `SELECT count(*) FROM students` is 1898. A second run updates those rows.
4. Still open. Compare one known user, including your own profile, between the sheet and `students`.
5. Switch `UserService` to the table only after that compare matches. Until then the bot keeps writing profiles to Sheets.

### Phase 4 — Content catalog

Started 13 Oct 2026 with `content_items` only. `folders` waits until this table is in the database and the Index dry-run has been read.

`content_items` is one Drive file. The primary key is `drive_file_id`, the Index column `File ID`. There is no sequence. Level, subject, type, and topic are stored as the folder text the sync wrote. A path `Class 12/AI/Notes/Computer Vision` becomes level `Class 12`, subject `AI`, type `Notes`, topic `Computer Vision`. Those values are not checked against the student subject list. `Computer Vision` was rejected on `students` because it is not a profile subject. On this table it is a valid topic.

1. Read `migrations/versions/20261013_0004_create_content_items.py`, then apply it:

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
export DATABASE_URL='postgresql://bot:bot@127.0.0.1:5433/ask_ai'
pipenv run alembic current
pipenv run alembic upgrade head
pipenv run alembic current
psql "postgresql://bot:bot@127.0.0.1:5433/ask_ai" -c "\d content_items"
```

`current` moves from `20261013_0003` to `20261013_0004`. `\d content_items` shows `drive_file_id` as the primary key, with an empty Default, and the index `ix_content_items_level_subject_type`.

2. Done on 13 Oct 2026. Dry-run: `scanned` 203, `valid` 203, `rejected` 0. `--apply` imported 203 rows. `SELECT count(*) FROM content_items` is 203.

3. `folders` is one Drive folder. The primary key is `drive_folder_id`. `path` is unique because a notes request builds one path, such as `Class 10/AI/Notes`, and expects one URL. Read `migrations/versions/20261013_0005_create_folders.py`, then apply it:

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
export DATABASE_URL='postgresql://bot:bot@127.0.0.1:5433/ask_ai'
pipenv run alembic current
pipenv run alembic upgrade head
pipenv run alembic current
psql "postgresql://bot:bot@127.0.0.1:5433/ask_ai" -c "\d folders"
```

`current` moves from `20261013_0004` to `20261013_0005`. `\d folders` shows `drive_folder_id` as the primary key, with an empty Default, and unique constraint `uq_folders_path`.

Done on 13 Oct 2026. Dry-run: `scanned` 95, `valid` 95, `rejected` 0. `--apply` imported 95 rows. `SELECT count(*) FROM folders` is 95.

4. Done in code on 13 Oct 2026. `BOT_DATA_STORE=postgres` uses `PostgresUserService` and `PostgresNoteRepository`. The default is `sheet`, so a restart without the flag still reads Google Sheets. The Drive sync job still writes the Index and Folders sheets. A profile saved while the flag is `postgres` is written only to `students`.

### Warnings — the last sheet the bot reads back

Not applied. This is the table that has to land before the hundred cases. A warning is one student in one group. The sheet columns are `user_id`, `chat_id`, `username`, `warning_count`, `last_reason`, `last_warning`, `banned`. The second warning in that chat is a ban. The same person in another chat is a different row, so the primary key is both ids. Neither id is generated by Postgres.

`ModerationLogs` is not a table. The function that would write it is never called. `DriveSyncLogs` is an audit the sync job appends and the bot never reads back. YouTube, the PDF bytes, and `pgvector` are not tables in this pass. Old `Logs` rows go into `interaction_events` later, after the timestamp timezone is confirmed. That copy is not required to test the live bot.

1. Read `migrations/versions/20261013_0006_create_warnings.py`, then apply it:

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
export DATABASE_URL='postgresql://bot:bot@127.0.0.1:5433/ask_ai'
pipenv run alembic current
pipenv run alembic upgrade head
pipenv run alembic current
psql "postgresql://bot:bot@127.0.0.1:5433/ask_ai" -c "\d warnings"
```

`current` moves from `20261013_0005` to `20261013_0006`. `\d warnings` shows `telegram_user_id` and `telegram_chat_id` as the primary key, both with an empty Default, and check `ck_warnings_count_nonnegative`.

2. Done on 13 Oct 2026. Second dry run: `scanned` 177, `valid` 163, `collapsed` 14, `rejected` 0. The collapsed rows are one student in one chat. The highest count, 13 and banned, is the row that will be imported. A later row with a lower count is the lookup bug, not an unban.

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
pipenv run python scripts/copy_warnings.py --source-timezone UTC
```

3. Done on 13 Oct 2026. The dev bot logged `Profiles, notes, folders, and warnings are read from Postgres`. A private "notes" reply returned the Class 12 AI Drive folder. The Postgres log insert took 13 milliseconds. No group message ran, so this restart did not read or write `warnings`.

### Drive sync into the catalog

Not run. `scripts/sync_catalog.py` lists Drive and, only with `--apply`, replaces `content_items` and `folders`. The Index and Folders sheets stay as they are. An empty listing is refused, because a Drive API error returns no files and must not delete the 203 copied rows. `/sync` uses the same replace when the flag is `postgres`. The five-minute job is not scheduled in this dev install.

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
pipenv run python scripts/sync_catalog.py
```

Done on 13 Oct 2026. Dry run listed 222 files and 93 folders. `--apply` replaced the tables. Counts are now 222 and 93. `Class 12/AI/Notes` is still folder id `129Kuy43zVF-eeDATsmGEi7xailM0FW7M`. The four Class 12 AI topic folders that are no longer in Drive were removed with their four PDFs. `Class 10/AI/Notes/2026` and `Class 10/AI/Notes/2027` were added.

### Phase 5 — One hundred scripted cases

The no-model pass ran on 13 Oct 2026. `scripts/exercise_postgres.py` checked 82 folder lookups, all 222 files, 100 fake students, 4 warning checks, and 100 log rows. `failed` was 0. The fake rows were deleted. Real counts stayed at 1,898 students, 163 warnings, 222 files, and 93 folders.

The live pass ran on 14 Oct 2026 in private chat with user `8405510906`. Postgres log inserts were about 6 milliseconds. No errors.

| Message | Result |
| --- | --- |
| Give me notes | Class 12 AI notes folder `129Kuy43zVF-eeDATsmGEi7xailM0FW7M` |
| Video | 8 YouTube results |
| What's my class and subject | Class 12 AI, then Class 11 IT after the update |
| Change class to 11 and subject to IT | `students` row updated |
| Sample papers while subject was IT | No Class 11 IT sample papers exist |
| Change subject to AI | `students` row is class 11, subject AI, `last_updated` 2026-10-14 20:04:17 UTC |
| Sample papers | Class 11 AI folder `11MLlzrCM8-LlGBultFarsg8RNtaD428g`, path `Class 11/AI/Sample Question papers SQP` |

Class 11 sample papers exist for AI, CS, and IP only. The sample-paper name fix resolved the lowercase `papers` folder. A group-chat strike has not been sent.

Each case is a fake user id and a message: notes, videos, sample papers, a profile update, a follow-up that should use the saved class and subject. The script calls the same profile and notes code the bot uses.

| Check | Pass |
| --- | --- |
| New id | `students` row with NULL class and subject |
| "I'm in class 12 CS" | That row updates. The next "notes" message from the same id uses 12 and CS |
| Catalog | Files match `content_items` for that class, subject, and type |
| Videos | The reply contains YouTube results for the topic. This checks the tool, not a table |
| Log | One `interaction_events` row per case |

Run the profile and catalog checks with no model first. Then a small live set. Then the full 100. Live cases call the model and spend API credits. Score "right tool and right class/subject". The model's wording will vary.

The cases include a warning in a group chat. That check uses `warnings`.

### Phase 6 — Merge

Not started. Merge after Phase 5 passes.

Production stays on `INTERACTION_LOG_MODE=sheet`. The local `DATABASE_URL` stays in `.env` and is not a Cloud Run secret. `main` then contains the code. It does not contain a database.

### Phase 7 — Supabase and cutover

Started 16 Oct 2026. The project exists and the tables are loaded. Production is not pointed at it. Follow `docs/INTERACTION_LOGGING.md` for the cutover gates.

1. Done. The Supabase project is in Mumbai on the Free plan. This PC reaches it through the session pooler on port 5432 because the direct host is IPv6-only.
2. Not done. Store the port 6543 pooler URL in Secret Manager as `database-url` when Cloud Run should connect. Do not put that URL in the dev `.env`.
3. Apply the same migrations. `alembic current` must match local head.
4. Smoke-test one private message in `dual` mode. The same `event_id` appears in Sheet column H and in Postgres.
5. Do not backfill historical `Logs`. ADR-019. Dual-write new messages for 3–4 days that include a busy period, then compare those new rows.
6. Done for the first load on 16 Oct 2026: 1,900 profiles, 163 warnings, 222 files, 93 folders. Copy profiles and warnings again at cutover so rows edited after today are included. Schedule the five-minute Drive sync only after `database-url` is set.
7. Switch reads to `postgres`. Keep dual log writes until the 3–4 day compare is clean.
8. Stay on the Free plan. ADR-020. Run `scripts/backup_postgres.py` weekly against the direct URL and keep the file off the project. Free pauses after about a week without database use. The live bot is what keeps it awake. The local restore drill already passed on 14 Oct 2026.

## Data stores during the move

| Store | What it holds now | What you protect |
| --- | --- | --- |
| Local Postgres `ask_ai` | `interaction_events`, and `students` after Phase 3 | Disposable. Do not point Cloud Run here |
| Google Sheets | Profiles, Index, Folders, Warnings, and production logs | Still the source for everything except the local log experiment |
| Google Drive | PDF and other files | The catalog points at these ids. Do not move the files in this migration |
| YouTube | Video search | API key stays in Secret Manager or `.env` |
| Supabase | Nothing yet | Pooled URL in `database-url`. Direct URL never stored in that secret |

## Security

- `.env` is gitignored. It holds the local `DATABASE_URL` and the bot tokens.
- Do not commit Sheet exports, reject files, or dumps. `artifacts/` is gitignored because those files contain messages and Telegram ids.
- Production TLS is `sslmode=require`. Localhost does not use TLS.
- Raw messages are personal data. The runbook's retention rule is 180 days, enforced by a reviewed job before Postgres is the only log store. That job is not written yet.

## Suggested order of work

1. Done. `BOT_DATA_STORE=postgres` reads profiles, the catalog, and folders.
2. Done. `warnings` has 163 rows. The dev bot restart read profiles, notes, folders, and warnings from Postgres.
3. Done. Drive sync replaced the catalog. `content_items` is 222 and `folders` is 93.
4. Done. The no-model exercise passed: 82 folders, 222 files, 100 fake students, warnings, and 100 log rows. Fake rows were deleted.
5. Done on 14 Oct 2026. Live private messages covered notes, videos, profile updates, and sample papers.
6. Done on 14 Oct 2026. `scripts/backup_postgres.py --restore-drill` wrote a dump and loaded it into a temporary database. The check matched revision `20261013_0006`, 1,898 students, 222 files, 93 folders, 163 warnings, and 22 log rows. The temporary database was dropped. The dump stays in gitignored `artifacts/`.
7. Phase 7. Supabase Free, fresh sheet copy, Drive sync, dual-write, then merge with production left on Sheets until the flags change.

## Open points to edit when you decide

- Whether the students copy runs while the bot is still writing new profiles to Sheets, and how a profile edited during the copy is caught.
- Whether a group-chat strike is part of the 100 cases. `warnings` is already copied.
- Historical `Logs` are not copied. Decided 14 Oct 2026. The sheet stays the archive. Dual-write covers new messages. ADR-019.
- Supabase Free is enough for the first live database. A weekly `pg_dump` is the backup. ADR-020. `scripts/backup_postgres.py` passed a local restore drill on 14 Oct 2026. Point it at the Supabase direct URL after the project exists. Do not use the pooler for the dump.
- The two rejected profiles stay rejected. Subject `Computer Vision` and subject `Banking` are not student subjects.
- When the Supabase URL exists, copy `UserProfiles` and `Warnings` again for the latest rows, then run the Drive sync. Do not replace the catalog from the Index sheet. The five-minute sync is scheduled after that URL exists.
