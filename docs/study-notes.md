# Study notes — what was built and why

Read this later as a walkthrough of the Postgres work from 26 Sep 2026 through 13 Oct 2026. The design that is still ahead of you lives in `docs/postgres-migration-plan.md`. This file is what already happened, and what each piece means.

No passwords, bot tokens, or database URLs with passwords are written here. The local practice password lives only in `.env` and in the Docker container.

## The original goal

You wanted the bot's data in a real database instead of Google Sheets. Sheets is slow, rate-limited, and awkward to query. The older Phase 1 plan in `.cursor/plans/02-phase-1-supabase-migration.md` tried to move profiles, logs, the content index, folders, and warnings in about two weeks, through `supabase-py` and one `USE_SUPABASE` flag.

The work that actually landed is narrower. The Mac commit moves the interaction log first, through SQLAlchemy and Alembic, and leaves every other Sheet in place. On this PC you then proved that split with the dev bot, and started the next table, `students`.

## How the plan changed

These were decisions, in the order they were made.

1. The database is Supabase PostgreSQL in Mumbai, a project of its own, not the academy platform's project. ADR-002.
2. The bot does not call `supabase-py`. It uses `DATABASE_URL`, SQLAlchemy async, asyncpg, and Alembic, so the same code can talk to local Postgres, Supabase, Neon, or Cloud SQL. ADR-011, in the Mac commit.
3. Phase 1 is the interaction log only. Profiles, notes, warnings, folder mappings, and conversation memory stay where they are until a later migration.
4. Logging is fail-open. A failed insert must not stop the student reply. The mode flag is `INTERACTION_LOG_MODE`, default `sheet`.
5. One `event_id` is generated in the handler and shared by Sheets and Postgres. A retry with the same id is ignored. Sheets and Postgres cannot share a transaction.
6. Old Sheet timestamps are stored as raw text until a known interaction confirms their timezone. ADR-012.
7. Supabase Free is only for the period when Sheets is still a second copy. Free has no automatic backups and can pause after a week idle.
8. Content search stays on Gemini File Search. `pgvector` is for Mem0 student memory later, not for a big embeddings column on the notes catalog. ADR-006 and ADR-007.
9. On 3 Oct 2026 the next table was chosen: `students`, one row per Telegram user, matching the `UserProfiles` sheet. ADR-013. The bot was not switched to it.

## Step 1 — The Mac commit

Done 26 Sep 2026. Commit `2dfac84`, author Anuraj, message `feat: add PostgreSQL interaction migration foundation (ENG-79)`. Branch `feat/platformization/supabase-migration`, on top of `codex/platformization`. 34 files, about 3,700 lines.

You paused before any database URL, any Sheet edit, or any Cloud Run deploy. The handoff files (`.planning/HANDOFF.json` and `.planning/phases/01-supabase-migration/.continue-here.md`) say the work was uncommitted. That was true when they were written. The commit was made after that pause. Ignore the "uncommitted" sentence. The code is in git.

On the Mac, Docker was installed and the daemon was not running, so the six online Postgres tests were skipped. Offline checks were 21 passed. Ruff, a compile, and an Alembic SQL dump (SQL printed, not applied) were clean. No live database was contacted.

### What a log row is

`telegram_bot/domain/interactions.py` defines `InteractionEvent`. It is one private reply, frozen after it is created. The handler in `telegram_bot/handlers.py` builds it. `event_id` is a UUID created there. `occurred_at` comes from the Telegram message time and must include a timezone.

`InteractionRepository` is the interface "save this event." Two classes implement it:

| File | What it writes |
| --- | --- |
| `telegram_bot/infrastructure/postgres_interaction_repository.py` | `INSERT` into `interaction_events`. `on_conflict_do_nothing()` skips a duplicate `event_id` |
| `telegram_bot/infrastructure/sheets_interaction_repository.py` | One appended row on the `Logs` worksheet, including the same `event_id` |

`telegram_bot/services/interaction_logging_service.py` picks the destination from the mode:

| Mode | Where the row goes |
| --- | --- |
| `sheet` | Google Sheets only. This is the default, including production today |
| `dual` | Sheets and Postgres. The report is a success only when both writes succeed |
| `postgres` | Postgres only |
| `off` | Nowhere |

Each write has its own 5 second timeout. A failure is logged. The Telegram reply still goes out.

`telegram_bot/infrastructure/database.py` turns `DATABASE_URL` into a pool of connections. A pool is a handful of connections kept open and reused, so each message does not pay to connect from scratch. `healthcheck()` runs `SELECT 1`. `main.py` builds this pool at startup when the mode is `postgres` or `dual`, stores the logging service for the handler, and closes the pool on shutdown. If the URL is missing or the health check fails, startup continues and logging reports the failure. The bot still answers.

### The migration

A migration is a reviewed Python file that changes the database. Alembic runs those files in order and stores the latest revision id in a table called `alembic_version`.

`migrations/versions/20260922_0001_create_interaction_events.py` creates `interaction_events`. `upgrade()` creates it. `downgrade()` drops it. `alembic.ini` points Alembic at the `migrations/` directory. `migrations/env.py` reads `DATABASE_URL` and connects with asyncpg.

The columns are the seven `Logs` sheet columns plus identity fields:

| Column | Meaning |
| --- | --- |
| `event_id` | Primary key. Generated in Python before either write |
| `telegram_update_id` | Telegram's id for this update. Unique, so a webhook retry does not insert twice. NULL for a historical row that has no update id |
| `telegram_user_id` | The student's Telegram id |
| `occurred_at` | When the interaction happened, UTC, with a timezone |
| `user_message`, `bot_response` | The text |
| `screener_output`, `intent_output`, `entities_output` | Copied from the old sheet shape. See step 4 for what the current bot puts here |
| `source_ref` | Set only when an old sheet row is imported. Live messages leave it empty |
| `source_timestamp_raw` | The original sheet timestamp text, untouched |
| `created_at` | When this database row was inserted |

Indexes are on `occurred_at` and `telegram_user_id`, which are the filters you will actually use.

### Settings and deploy

`config/settings.py` reads `INTERACTION_LOG_MODE`. Allowed values are `sheet`, `dual`, `postgres`, and `off`. The default is `sheet`.

`DATABASE_URL` comes from the environment. In `dual` or `postgres` mode the app also looks for a Secret Manager secret named `database-url`. On your PC, `.env` supplies the variable and Secret Manager is not involved. `.env` is gitignored.

`deploy.sh` was changed from `--set-env-vars` to `--update-env-vars` for `GCP_PROJECT_ID`. `--set-env-vars` replaces the whole environment list. `--update-env-vars` changes one variable and leaves `INTERACTION_LOG_MODE` alone. That matters once production has a mode set. This branch has not been deployed.

Pool defaults: `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2`, `DB_POOL_TIMEOUT_SECONDS=10`, `INTERACTION_WRITE_TIMEOUT_SECONDS=5`. Each Cloud Run instance opens its own pool. The small numbers are there so several instances fit inside Supabase's pooler.

### Scripts that exist and have not been run against production

| Script | What it does |
| --- | --- |
| `scripts/backfill_sheet_interactions.py` | Copies a frozen `Logs` export into Postgres. `--apply` is the only mode that writes. Without it, the script only validates |
| `scripts/reconcile_interaction_logs.py` | Read-only compare of sheet rows and Postgres rows: event ids, seven field hashes, and application logs |
| `scripts/interaction_log_migration.py` | Shared parsing for those two scripts |

`docs/INTERACTION_LOGGING.md` is the runbook: secret creation, Alembic, dual-write, backfill, the 3–7 day watch, the restore drill, and rollback by changing the flag back to `dual` or `sheet`. It tells you not to drop the schema or delete rows as a rollback.

### Tests in that commit

`tests/conftest.py` can start a throwaway Postgres in Docker, or use `TEST_DATABASE_URL` if you set it. The fixture runs `alembic downgrade base` and then `upgrade head`. Point it only at an empty database. A shared or production URL would be wiped.

The Mac run did not have that database, so `tests/integration/test_postgres_interactions.py` was skipped. Unit tests for the logging service, the handler, startup, and the migration scripts did run.

## Step 2 — A Postgres server on this PC

Done 3 Oct 2026, before the dev-bot check.

This PC already has PostgreSQL 18 listening on port 5432. That is a system service. This project does not use it. The project database is a Docker container so it can be deleted without touching anything else.

Docker runs Postgres inside a container. The container is named `ask-ai-postgres`. The image is `pgvector/pgvector:pg16`: Postgres 16 plus the `vector` extension, which is not turned on. Using that image means a later migration can run `CREATE EXTENSION vector` for Mem0 without building a new server.

The published port is `127.0.0.1:5433`. Inside the container Postgres still listens on 5432. The mapping forwards only this PC's port 5433 to that internal port. `127.0.0.1` means other machines cannot connect. Port 5433 was chosen because 5432 was already taken.

The first start creates user `bot` and database `ask_ai` from the container's environment variables. The password is the local practice password. It is not a Supabase password.

Create it, from this PC:

```bash
docker rm -f ask-ai-postgres
docker run --name ask-ai-postgres \
  -e POSTGRES_USER=bot \
  -e POSTGRES_PASSWORD=bot \
  -e POSTGRES_DB=ask_ai \
  -p 127.0.0.1:5433:5432 \
  -d pgvector/pgvector:pg16
docker exec ask-ai-postgres pg_isready -U bot -d ask_ai
```

`pg_isready` should say `accepting connections`.

`psql` is the text client. `\l` lists databases. `\dt` lists tables. The first `\dt` on a new database says no tables exist. The bot does not create tables. Alembic does.

Apply the Mac migration with the project Pipenv, not the older virtualenv under `/home/jimmy/ASK AI/venv`. That older environment does not have SQLAlchemy. Pipenv's environment is `telegram-bot-akask-ALMArvcg` under `~/.local/share/virtualenvs/`.

```bash
cd "/home/jimmy/ASK AI/telegram-bot-akask"
export DATABASE_URL='postgresql://bot:bot@127.0.0.1:5433/ask_ai'
pipenv run alembic upgrade head
pipenv run alembic current
```

After this step, and before the students migration, `current` prints `20260922_0001`. `\d interaction_events` prints the columns. `SELECT * FROM interaction_events` returns zero rows. `alembic_version` holds the revision id.

Stop and start without deleting data:

```bash
docker stop ask-ai-postgres
docker start ask-ai-postgres
```

`docker rm -f ask-ai-postgres` deletes the rows. You would run `alembic upgrade head` again after creating the container.

On Supabase this step is the same command with a different URL. Alembic uses the direct URL. The running bot uses the pooled URL. Locally there is no pooler, so one URL does both. Supabase also requires TLS (`sslmode=require`). Localhost does not.

## Step 3 — The dev bot wrote a real log row

Confirmed 3 Oct 2026. You ran the dev bot. It loaded your profile and your notes from Google Sheets, and it wrote the interaction to local Postgres.

That is the split this branch is built for.

`.env` gained two settings (the file is gitignored, so they are not in the commit):

```text
INTERACTION_LOG_MODE=postgres
DATABASE_URL=postgresql://bot:bot@127.0.0.1:5433/ask_ai
```

`postgres` means the log goes only to Postgres. The profile read and the notes read are separate code. `UserService` still opens the `UserProfiles` worksheet. Notes still open the `Index` and `Folders` worksheets and then the file in Drive. Videos, if you ask for them, call YouTube. None of those paths look at `interaction_events`.

Startup logs `Interaction logging initialized: mode=postgres database_ready=True` when the pool's `SELECT 1` succeeds.

A practice insert script, `scripts/dev_insert_sample_event.py`, uses the same repository as the bot. It inserts one fake row and inserts it again. The second call returns `inserted_again False` because the `event_id` collides and Postgres skips it. That is the retry behavior. The script is a local exercise. It is not part of the Mac commit.

Look at real rows:

```bash
psql "postgresql://bot:bot@127.0.0.1:5433/ask_ai" \
  -c "SELECT event_id, telegram_user_id, left(user_message, 80) AS user_message, intent_output, occurred_at FROM interaction_events ORDER BY created_at DESC LIMIT 5;"
```

You should see your Telegram user id, your message, and `intent_output` of `agent`. `source_ref` is empty on a live message.

### The dev server port

`start_devtest.sh` used to kill every process on port 8080, then start the bot there. This PC also runs Odysseus, and SearXNG is published on `127.0.0.1:8080`. Killing that port takes SearXNG down.

The script now stops only a previous `uvicorn main:app` from this project. If 8080 is taken, it tries 8081, then 8082, 8888, then 8090, and points ngrok at whichever port it kept. If the server process dies during startup, the script prints the last log lines from `/tmp/telegram-bot-server.log` and exits. This change is in the working tree. It is not in `2dfac84`.

## Step 4 — Screener, intent, and entities

You asked what `screener_output` and `entities_output` are after looking at a live row.

The old bot wrote seven columns to `Logs`: timestamp, user id, user message, bot reply, screener, intent, and entities. The old pipeline meant:

- **Screener** — a safety check before the answer. Typical old values were an allow or a block reason.
- **Intent** — what the student wanted: notes, a video, an explanation.
- **Entities** — details pulled from the message, such as class 10 and subject AI.

About 14,470 historical rows have those columns. The Postgres table keeps all three as plain text so a later copy does not have to invent JSON. Old cells are not reliable JSON. ADR-012 is the same idea for timestamps: store the source text, convert only when you know the timezone.

The current bot does not run that classifier. `telegram_bot/runtime/chat_runtime.py` sets `intent` to `agent` on a normal private reply. The handler then looks for `screener_output` and `entities_output` in the response metadata, finds neither, and stores an empty string. Moderation still runs, and a flagged message has a category in metadata, but that category is not copied into `screener_output`.

So a row from your dev bot has empty screener and entities, and intent `agent`. An imported historical row will have whatever the sheet cell contained.

## Step 5 — The `students` table

Started 3 Oct 2026. Applied on this PC and inspected with `\d students` on 13 Oct 2026.

A log row is one message and is never updated. A student row is one person and is updated when they set a class or subject. Many log rows belong to one student. The bot still does not read or write this table. `UserService` in `telegram_bot/services/user_service.py` is unchanged and still uses the sheet.

The sheet columns, from `_create_worksheet` in that file, are:

```text
user_id, username, current_class, preferred_subject, created_at, last_updated, class_updated_year
```

`get_user_profile` finds the Telegram id in column 1. If the row is missing, it appends one with a blank class and subject. `class_updated_year` is the year used by the June promotion: after 1 June, if the stored year is older than this year and the class is below 12, the class goes up by one.

The new files:

| File | What it is |
| --- | --- |
| `migrations/versions/20261003_0002_create_students.py` | Alembic revision. `down_revision` is `20260922_0001`, so applying it does not rebuild `interaction_events` |
| `telegram_bot/infrastructure/postgres_students.py` | The same table described for Python, on the shared SQLAlchemy metadata |
| `tests/integration/test_postgres_students.py` | Inserts a valid profile, a profile with NULL class and subject, and expects class `9` and subject `Math` to be rejected |
| `migrations/env.py` | Imports the students table so Alembic's metadata includes it |
| `DECISIONS.md` | ADR-013 |

`telegram_user_id` is the primary key. There is no second numeric id. A Discord-only or website-only account would need a later migration. Those accounts do not exist in the sheet, so they are not columns yet.

`current_class` is NULL or one of 10, 11, 12. `preferred_subject` is NULL or one of AI, CS, IT, IP. NULL means "not chosen," which is how a new sheet row looks when class and subject are blank. A blank subject is not stored as an empty string, because the check would reject it. Username may be an empty string. The two checks are named `ck_students_current_class` and `ck_students_preferred_subject`.

The integration test that used to expect Alembic head `20260922_0001` now expects `20261013_0004`. The same revision string is in `docs/INTERACTION_LOGGING.md`, in the cutover checklist and in the restore-drill snippet. The local database stays at `20261013_0003` until you apply `20261013_0004`.

On 13 Oct 2026 `\d students` showed the seven columns, primary key `pk_students`, and both checks. It also showed this default on `telegram_user_id`:

```text
nextval('students_telegram_user_id_seq'::regclass)
```

SQLAlchemy treats a single integer primary key as an identity column and creates that sequence. An insert that forgets the Telegram id would then store 1, then 2, then 3. Those are not Telegram ids. `migrations/versions/20261013_0003_students_telegram_id_no_sequence.py` drops the default and the sequence. The Python column sets `autoincrement=False` so the table definition matches. Applied on 13 Oct 2026. `\d students` now leaves Default empty for `telegram_user_id`.

The copy script is `scripts/copy_student_profiles.py`. On 13 Oct 2026 the dry run reported `scanned` 1900, `valid` 1898, `rejected` 2. Row 216 stored subject `Computer Vision`. Row 306 stored subject `Banking`. The profile check refused both. `--apply` then inserted 1,898 rows. `SELECT count(*) FROM students` is 1898. `UserService` still reads and writes the sheet. A profile created after this copy is not in Postgres until the script is run again.

## Step 6 — The `content_items` table, in code

Started 13 Oct 2026. Migration `20261013_0004` is applied. The Index dry-run reported 203 valid rows and 0 rejected. `--apply` then inserted 203 rows. `SELECT count(*) FROM content_items` is 203. The bot still reads the Index sheet.

The Index sheet is the catalog of Drive files. `SyncService._parse_metadata` splits a Drive path:

```text
Class 12/AI/Notes/Computer Vision
  level          Class 12
  subject        AI
  type           Notes
  topic          Computer Vision
```

The sheet columns are `Title`, `Link`, `Level`, `Subject`, `Type`, `Topic`, `File ID`. The new table `content_items` uses `drive_file_id` as the primary key. It is text, so Postgres does not create a sequence. Level, subject, type, and topic are stored as that folder text. There is no check that subject is AI, CS, IT, or IP. `Computer Vision` is a topic here, which is why it was rejected on `students` and is valid on this table. The file itself stays in Drive.

`migrations/versions/20261013_0004_create_content_items.py` follows `20261013_0003`. `scripts/copy_content_items.py` reads the Index worksheet with `service_account.json`. Dry-run is the default. ADR-014 records the decision.

## Step 7 — The `folders` table, in code

Started 13 Oct 2026. Migration `20261013_0005` is applied. The Folders dry-run reported 95 valid rows and 0 rejected. `--apply` then inserted 95 rows. `SELECT count(*) FROM folders` is 95.

`NoteService.get_folder_link` builds a path such as `Class 10/AI/Notes` or `Class 10/AI/Notes/NLP` and looks for that text in the Folders sheet. The sheet columns are `Path`, `Folder ID`, and `URL`. The sync fills them from Drive folders. The URL is `https://drive.google.com/drive/folders/` plus the folder id.

`folders` uses `drive_folder_id` as the primary key and requires `path` to be unique. A notes request must not find two URLs for one path. The migration is `20261013_0005`. `scripts/copy_folders.py` reads the worksheet with `service_account.json`. Dry-run is the default. ADR-015 records the decision.

## Step 8 — The bot can read the copied tables

`BOT_DATA_STORE` chooses the source for profiles, the notes catalog, and folder links. The default is `sheet`. Production is unchanged until the flag is set.

`postgres` constructs `PostgresUserService` and `PostgresNoteRepository` in `telegram_bot/application.py`. They share one connection pool. A new student is inserted into `students`. A class or subject update writes there too. Notes are loaded from `content_items` into the same tag order the sheet used: level, subject, type, topic. Folder links come from `folders`. When several paths match a request that has no topic, the shortest path wins, so `Class 10/AI/Notes` is chosen ahead of `Class 10/AI/Notes/Computer Vision`.

Warnings and the five-minute Drive sync still use Google Sheets. A sync does not refresh `content_items` or `folders`. ADR-016 records the flag.

Add this line to `.env` and restart the dev bot:

```text
BOT_DATA_STORE=postgres
```

The startup log should include `Profiles, notes, and folders are read from Postgres`.

On 13 Oct 2026 a "Give me notes" reply took about 26 seconds and still returned the Class 12 AI Drive folder. The folder lookup and the Postgres log insert were not the wait. The log insert finished in 9 milliseconds. `get_notes` finished in the same millisecond it was called. About 23 seconds was the moderation request to `api.openai.com` before the agent started. OpenAI reported about 2 seconds of processing for that check. The agent call after it took about 2 seconds. A slow reply on this path is the model call, not the local tables.

## What you can open

| What | Where |
| --- | --- |
| This branch | `feat/platformization/supabase-migration` |
| Mac commit | `2dfac84` |
| Local database | `127.0.0.1:5433`, database `ask_ai`, user `bot` |
| Log table | `interaction_events` |
| Students table | 1,898 rows |
| Content catalog | 222 rows in `content_items` after the Drive sync |
| Folders | 93 rows after the Drive sync |
| Warnings | 163 rows. 14 extra sheet rows for one student were collapsed to the highest count |
| Bot data source | `BOT_DATA_STORE` defaults to `sheet`. Set `postgres` in `.env` to read the copied tables |
| Dev bot | `./start_devtest.sh`. Port 8080, or the next free port if SearXNG has 8080 |
| Log runbook | `docs/INTERACTION_LOGGING.md` |
| Living plan | `docs/postgres-migration-plan.md` |

## Step 9 — The `warnings` table, in code

The Warnings sheet is the last worksheet the bot reads back while answering. One row is one student in one chat. The columns are `user_id`, `chat_id`, `username`, `warning_count`, `last_reason`, `last_warning`, and `banned`. The second warning in that chat bans the student. A different chat is a different row, so the primary key is both ids.

`ModerationLogs` is unused code. `DriveSyncLogs` is a sync audit the bot does not read. Neither becomes a table. YouTube and the PDF files stay where they are. Old log rows are a later copy into `interaction_events`, after the sheet timezone is confirmed.

The migration is `20261013_0006`. `scripts/copy_warnings.py` reads the worksheet with `service_account.json`. Dry-run is the default and needs `--source-timezone`, because `last_warning` on the sheet has no offset. ADR-017 records the decision. The same `BOT_DATA_STORE=postgres` flag reads this table after the migration is applied and the dev bot is restarted.

The first dry run on 13 Oct 2026 scanned 177 rows. 14 were the same student in chat `-1003903542050`. The sheet appended a new row each warning because lookup stops at that student's other chat. Counts ran from 1 up to 13, banned, on 24 Sep 2026, then two later rows reset the count to 1. The copy keeps the highest count for each user and chat, so that chat is stored as 13 warnings and banned. The other chat for the same student stays at 1. The second dry run reported `valid` 163, `collapsed` 14, `rejected` 0. `--apply` then imported 163 rows. The dev bot restart logged that profiles, notes, folders, and warnings are read from Postgres. A private notes reply returned the Class 12 AI folder and the log insert took 13 milliseconds. That reply did not read `warnings`.

## Step 10 — Drive sync can refresh the catalog

The sync job used to clear the Index and Folders sheets and write them again from Drive. With `BOT_DATA_STORE=postgres` the bot does not read those sheets, so a new PDF would never show up. `scripts/sync_catalog.py` lists the same Drive tree. Dry-run prints how many files and folders it would write. `--apply` deletes the current `content_items` and `folders` rows and inserts the new snapshot in one transaction. If the listing is empty, the script stops and the copied rows stay. The sheets are not modified. ADR-018 records the decision.

The dev process does not schedule the five-minute sync, because the Telegram job queue extra is not installed. Run the script when you want a refresh. After an apply, restart the bot so it drops the catalog it already loaded.

The 13 Oct 2026 dry run listed 222 files and 93 folders. The copied tables had 203 and 95. Drive had gained `Class 10/AI/Notes/2026`, `Class 10/AI/Notes/2027`, and 23 files, mostly in those year folders and in `Class 12/CS/Notes`. Drive no longer had four Class 12 AI topic folders: Unit 1 Capstone Project, Unit 1 Communication Skills-IV, Unit 2 Model Lifecycle, and Unit 3 Storytelling Through Data. `--apply` replaced the tables. `content_items` is 222 and `folders` is 93. `Class 12/AI/Notes` is still folder id `129Kuy43zVF-eeDATsmGEi7xailM0FW7M`.

A sample-paper request asks for `Sample Question Papers`. Drive stored `Sample Question Papers SQP`, and Class 11 stored `Sample Question papers SQP`. Lookup treats those as the same resource, so the current rows answer the tool name without another sync.

## Step 11 — Live messages on 14 Oct 2026

User `8405510906` sent a private sequence on the dev bot. `INTERACTION_LOG_MODE` was `postgres`. Each insert succeeded in about 6 milliseconds. The log has no errors.

"Give me notes" returned the Class 12 AI folder `129Kuy43zVF-eeDATsmGEi7xailM0FW7M`. "Video" returned 8 YouTube results. "What's my class and subject" answered Class 12 AI. "Change my class to 11 and subject to IT" wrote `students`. The same question then answered Class 11 IT. Three sample-paper messages while the subject was IT said nothing was found. Class 11 has sample-paper folders for AI, CS, and IP only, and no IT catalog at all. "Change to AI" set `preferred_subject` to AI at 2026-10-14 20:04:17 UTC. The next sample-paper replies opened `Class 11/AI/Sample Question papers SQP`, folder id `11MLlzrCM8-LlGBultFarsg8RNtaD428g`.

## Step 12 — The weekly dump

`scripts/backup_postgres.py` reads `DATABASE_URL` and does not print it. On this PC the database is the Docker container, so the script uses that container’s `pg_dump`. The computer’s own Postgres tools are newer and add a setting Postgres 16 does not understand. `--restore-drill` loads the dump into `ask_ai_restore_drill`, checks the counts, and drops that database. It does not touch `ask_ai`.

The 14 Oct 2026 run wrote `artifacts/ask-ai-20261014T202956Z.dump` (76,538 bytes). The restored check matched revision `20261013_0006`, 1,898 students, 222 files, 93 folders, 163 warnings, and 22 log rows. Run it again with `pipenv run python scripts/backup_postgres.py --restore-drill`. The same command later uses the Supabase direct URL. Do not point it at the pooler.

## What is not built yet

- A group-chat strike, so a live request reads and writes `warnings`. The private notes restart did not.
- One side-by-side check of your own profile: the `students` row against the UserProfiles sheet.
- The 100 scripted student messages.
- A Supabase project and the `database-url` secret. Historical `Logs` are not backfilled. Free tier plus a weekly `pg_dump` is the backup plan. `scripts/backup_postgres.py` passed a local restore drill on 14 Oct 2026. Profiles and warnings are copied again when the URL exists. The five-minute Drive sync waits for that URL.
- The 180-day retention job for raw messages.
- A merge to `main`. Production is still the Sheets log.

## File map

| Path | What it is |
| --- | --- |
| `docs/postgres-migration-plan.md` | The living design, including pieces not built yet |
| `docs/study-notes.md` | This file |
| `scripts/backup_postgres.py` | Weekly `pg_dump`. `--restore-drill` checks the archive and drops the temporary database |
| `docs/INTERACTION_LOGGING.md` | Operator runbook for the log table. Written in the Mac commit, revision id updated for `students` |
| `docs/SHEETS_TO_POSTGRES_MIGRATION_PLAN.md` | The Mac-era recommendation: log first, Free then Pro, dual-write rules |
| `.cursor/plans/02-phase-1-supabase-migration.md` | The older "move every sheet in two weeks" plan. Not what this branch implements |
| `DECISIONS.md` | ADR-011 and ADR-012 from the Mac commit. ADR-013 for `students` |
| `.planning/HANDOFF.json` | Pause note from the Mac. The "uncommitted" line is stale |
| `migrations/versions/20260922_0001_create_interaction_events.py` | Creates the log table |
| `migrations/versions/20261003_0002_create_students.py` | Creates `students`. Applied locally on 13 Oct 2026. Also created an unwanted id sequence |
| `migrations/versions/20261013_0003_students_telegram_id_no_sequence.py` | Drops that sequence. Applied locally on 13 Oct 2026 |
| `scripts/copy_student_profiles.py` | Copies `UserProfiles` into `students`. Applied locally: 1,898 rows, 2 rejected |
| `migrations/versions/20261013_0004_create_content_items.py` | Creates `content_items`. Applied locally. 203 rows imported, 0 rejected |
| `scripts/copy_content_items.py` | Copies the Index sheet into `content_items`. Applied locally |
| `migrations/versions/20261013_0005_create_folders.py` | Creates `folders`. Applied locally. 95 rows imported, 0 rejected |
| `scripts/copy_folders.py` | Copies the Folders sheet. Applied locally |
| `migrations/versions/20261013_0006_create_warnings.py` | Creates `warnings`. Applied locally. 163 rows imported, 14 collapsed |
| `scripts/copy_warnings.py` | Copies the Warnings sheet. Applied locally |
| `scripts/sync_catalog.py` | Replaces `content_items` and `folders` from Drive. Dry-run is the default |
| `telegram_bot/services/catalog_sync.py` | The Postgres replace. Refuses an empty Drive snapshot |
| `telegram_bot/services/postgres_warning_service.py` | Warning reads and writes when the flag is `postgres` |
| `telegram_bot/services/postgres_user_service.py` | Profile reads and writes for `BOT_DATA_STORE=postgres` |
| `telegram_bot/infrastructure/postgres_note_repository.py` | Catalog and folder reads for that same flag |
| `telegram_bot/infrastructure/postgres_folders.py` | The folder table definition |
| `telegram_bot/infrastructure/postgres_content_items.py` | The content catalog table definition |
| `telegram_bot/infrastructure/database.py` | The connection pool |
| `telegram_bot/infrastructure/postgres_interaction_repository.py` | The log `INSERT` |
| `telegram_bot/infrastructure/postgres_students.py` | The students table definition |
| `telegram_bot/infrastructure/postgres_warnings.py` | The warnings table definition |
| `telegram_bot/services/interaction_logging_service.py` | Mode flag and fail-open writes |
| `telegram_bot/services/user_service.py` | Profiles. Still the `UserProfiles` sheet |
| `scripts/dev_insert_sample_event.py` | One local practice insert. Not part of the Mac commit |
| `start_devtest.sh` | Dev server and ngrok. Now avoids port 8080 when SearXNG is using it |

Do not commit `.env`, Sheet exports, or database dumps.
