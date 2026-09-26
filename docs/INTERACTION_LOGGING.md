# Interaction logging

The interaction log stores one immutable event after a private Telegram reply.
`event_id` is generated once in the handler and is shared by PostgreSQL and the
temporary Google Sheets sink. PostgreSQL retries are idempotent on `event_id`,
`telegram_update_id`, and historical `source_ref`.

## Configuration and migration

Use `INTERACTION_LOG_MODE=sheet|dual|postgres|off`. `sheet` is the default until
dual-write is verified. `DATABASE_URL` is the only provider-specific database
setting used by the application; both `postgresql://` and
`postgresql+asyncpg://` schemes are accepted. Use a pooled URL at runtime and a
direct URL for Alembic when the provider distinguishes them.

For local PostgreSQL:

```bash
docker run --name ask-ai-postgres --rm \
  -e POSTGRES_USER=bot -e POSTGRES_PASSWORD=bot \
  -e POSTGRES_DB=ask_ai -p 127.0.0.1:5432:5432 \
  -d postgres:16-alpine
export DATABASE_URL='postgresql://bot:bot@127.0.0.1:5432/ask_ai'
pipenv run alembic upgrade head
```

Apply the same command to a non-production PostgreSQL database before
production. Store the production `database-url` in Secret Manager, restrict it
to the bot service account, and require TLS in the provider connection URL.
Never commit database credentials.

During the temporary migration, set `INTERACTION_LOG_MODE=dual`. Each sink is
reported separately and failures never fail the Telegram response. A dual
write is reported complete only when both writes succeed. Switch to
`postgres` only after later backfill and reconciliation work passes; rollback
is a flag change to `dual` or `sheet`.

## Data contract and privacy

The event includes UTC-aware occurrence and creation timestamps, Telegram
update and user IDs, raw user and bot messages, screener/intent/entity text,
and optional import source reference. Raw messages and Telegram IDs are
personal data:

- retain raw interaction events for 180 days, then delete them with a reviewed
  retention job before PostgreSQL becomes the sole store;
- grant database access only to the runtime and named maintainers;
- require encrypted transport outside local development;
- never include message bodies, Telegram user IDs, or connection URLs in
  application logs or error reports.

New Sheet timestamps are ISO 8601 with an explicit offset. Historical Sheet
timestamps were written with `datetime.now()` and no offset, so their timezone
may vary between local and Cloud Run writers. Backfill must retain each raw
timestamp and must not convert historical rows until a known sample confirms
the applicable timezone. The migration commands therefore require an explicit
IANA timezone and store the original text in `source_timestamp_raw`.

## Historical backfill

First export `Logs` as CSV without sorting or editing it. Record the Sheet ID
and the inclusive row number that existed immediately before dual-write. The
first seven headers must remain `Timestamp, User ID, User Message, Bot
Response, Screener, Intent, Entities`; a dual-write export may also have
`Event ID` as column eight.

Validate locally without database credentials or database writes:

```bash
python -m scripts.backfill_sheet_interactions \
  --csv artifacts/logs-snapshot.csv \
  --source-id "$SHEET_ID" \
  --source-timezone Asia/Kolkata \
  --end-row "$PRE_DUAL_WRITE_ROW" \
  --batch-size 500 \
  --rejects-file artifacts/interaction-backfill-rejected.csv
```

Review every rejected row. Once the timezone and snapshot watermark are
confirmed, apply the same snapshot to PostgreSQL:

```bash
export DATABASE_URL='postgresql://...'
python -m scripts.backfill_sheet_interactions \
  --csv artifacts/logs-snapshot.csv \
  --source-id "$SHEET_ID" \
  --source-timezone Asia/Kolkata \
  --end-row "$PRE_DUAL_WRITE_ROW" \
  --batch-size 500 \
  --rejects-file artifacts/interaction-backfill-rejected.csv \
  --apply
```

`--apply` is the only mode that writes PostgreSQL. Each row uses
`sheet:<sheet-id>:row:<row-number>` as `source_ref`, plus a deterministic UUID
when the row has no dual-write event ID. PostgreSQL conflict handling makes
the command safe to restart; `imported + skipped + rejected` must equal
`scanned`. Keep `--source-id`, the original CSV, and row numbering unchanged
on every rerun.

A read-only direct Sheet source is also supported when credentials are
available. It does not update any cells:

```bash
python -m scripts.backfill_sheet_interactions \
  --sheet-id "$SHEET_ID" --source-id "$SHEET_ID" --worksheet Logs \
  --credentials-file service_account.json \
  --source-timezone Asia/Kolkata \
  --end-row "$PRE_DUAL_WRITE_ROW"
```

Prefer a frozen CSV for the actual migration so appends during the run cannot
change its input.

## Payload reconciliation

After the representative dual-write window, make a new append-only export
containing the historical and dual-written rows. Reconciliation is read-only:

```bash
python -m scripts.reconcile_interaction_logs \
  --csv artifacts/logs-final.csv \
  --source-id "$SHEET_ID" \
  --source-timezone Asia/Kolkata \
  --historical-end-row "$PRE_DUAL_WRITE_ROW" \
  --dual-start 2026-09-22T12:00:00Z \
  --dual-end 2026-09-29T12:00:00Z \
  --batch-size 500 \
  --application-log artifacts/cloud-run-dual-write.log \
  --rejects-file artifacts/interaction-reconcile-rejected.csv \
  --report-file artifacts/interaction-reconciliation.json
```

Use the exact inclusive start and exclusive end of the exported dual-write
window. The command exits zero only when historical accounting is exact, no
source rows remain rejected, Sheet and PostgreSQL event-ID sets are identical
inside that window, all seven field hashes match, raw historical timestamps
match, and the supplied application logs contain observed PostgreSQL writes
with no failures. Reports contain identifiers and mismatched field names,
never message bodies. Inspect p50/p95/max write latency in the report before
changing `INTERACTION_LOG_MODE` to `postgres`.

## End-to-end operational runbook

Commands below assume:

```bash
export PROJECT_ID=telegram-bot-akask
export REGION=asia-south1
export SERVICE_NAME=telegram-bot
export RUNTIME_SERVICE_ACCOUNT="telegram-bot-user@${PROJECT_ID}.iam.gserviceaccount.com"
mkdir -p artifacts
```

Files under `artifacts/` are gitignored because snapshots, rejects, logs, and
reports may contain personal data. Keep them encrypted, access-restricted, and
delete them under the same 180-day retention policy.

### 1. Verify code and schema without a live database

```bash
pipenv install --dev
pipenv run python -m pytest -q tests/unit tests/test_interaction_migration_tools.py
pipenv run python -m compileall -q config telegram_bot scripts migrations tests main.py
DATABASE_URL='postgresql://offline:offline@127.0.0.1:5432/offline' \
  pipenv run alembic upgrade head --sql \
  > artifacts/alembic-upgrade-head.sql
```

Review the offline SQL. It must create `interaction_events`, both unique
constraints, both indexes, and the `alembic_version` row. Offline generation
does not prove connectivity or apply the schema.

### 2. Configure a disposable non-production database

Use a dedicated database with no production data. Either start the local
container shown above or set `TEST_DATABASE_URL` to an approved disposable
PostgreSQL URL, then run:

```bash
export TEST_DATABASE_URL='postgresql://...'
pipenv run python -m pytest -q tests/integration/test_postgres_interactions.py
unset TEST_DATABASE_URL
```

The integration fixture runs `alembic downgrade base` and therefore must never
receive a shared or production URL. A passing run must cover migration,
idempotency conflicts, Unicode/long text, nullable identifiers, and connection
failure behavior.

Apply the schema to a separate non-production application database using its
direct (not transaction-pooled) endpoint:

```bash
read -r -s -p "Non-production direct DATABASE_URL: " MIGRATION_DATABASE_URL
echo
DATABASE_URL="$MIGRATION_DATABASE_URL" pipenv run alembic upgrade head
DATABASE_URL="$MIGRATION_DATABASE_URL" pipenv run alembic current
unset MIGRATION_DATABASE_URL
```

Run a private-message smoke test in `dual` mode and verify one event has the
same `event_id` in Sheet column H and PostgreSQL before touching production.

### 3. Store and authorize production configuration

Create the secret container once:

```bash
gcloud secrets describe database-url --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud secrets create database-url \
    --project "$PROJECT_ID" \
    --replication-policy=automatic
```

Add the pooled runtime URL without putting it in source control or a command
argument:

```bash
read -r -s -p "Pooled runtime DATABASE_URL: " DATABASE_URL_INPUT
echo
printf '%s' "$DATABASE_URL_INPUT" | \
  gcloud secrets versions add database-url \
    --project "$PROJECT_ID" \
    --data-file=-
unset DATABASE_URL_INPUT
```

Grant only the Cloud Run service account access:

```bash
gcloud secrets add-iam-policy-binding database-url \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role=roles/secretmanager.secretAccessor
```

The application reads `database-url` through Secret Manager in Cloud Run.
`INTERACTION_LOG_MODE`, pool sizes, and timeouts are non-secret Cloud Run
environment variables. Keep `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2`,
`DB_POOL_TIMEOUT_SECONDS=10`, and `INTERACTION_WRITE_TIMEOUT_SECONDS=5`
initially. PostgreSQL URLs using `sslmode=require` are normalized for asyncpg;
TLS must remain required outside local development.

### 4. Back up sources and apply the production migration

Before changing the Sheet:

1. Export the untouched `Logs` worksheet to
   `artifacts/logs-snapshot.csv`.
2. Record its Sheet ID, export time, and highest inclusive data row as
   `PRE_DUAL_WRITE_ROW`.
3. Do not sort, edit, delete, or renumber rows.
4. Record a checksum:

```bash
shasum -a 256 artifacts/logs-snapshot.csv \
  > artifacts/logs-snapshot.csv.sha256
```

Use the provider's direct production endpoint only for the migration:

```bash
read -r -s -p "Production direct DATABASE_URL: " MIGRATION_DATABASE_URL
echo
DATABASE_URL="$MIGRATION_DATABASE_URL" pipenv run alembic upgrade head
DATABASE_URL="$MIGRATION_DATABASE_URL" pipenv run alembic current
unset MIGRATION_DATABASE_URL
```

This is an operator action requiring approved production access. Do not claim
it succeeded based on offline SQL or tests.

### 5. Deploy dual-write and backfill

Deploy the code with Sheets still active, then change only the feature flag:

```bash
gcloud run services update "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars='INTERACTION_LOG_MODE=dual,DB_POOL_SIZE=3,DB_MAX_OVERFLOW=2,DB_POOL_TIMEOUT_SECONDS=10,INTERACTION_WRITE_TIMEOUT_SECONDS=5'
```

Confirm the new revision is serving and `database_ready=True` appears without
credentials in logs. Send at least one private Telegram message and verify the
shared event ID and seven payload fields in both sinks.

Validate the frozen historical export first:

```bash
export SHEET_ID='<sheet-id>'
export PRE_DUAL_WRITE_ROW='<inclusive-row-number>'
pipenv run python -m scripts.backfill_sheet_interactions \
  --csv artifacts/logs-snapshot.csv \
  --source-id "$SHEET_ID" \
  --source-timezone Asia/Kolkata \
  --end-row "$PRE_DUAL_WRITE_ROW" \
  --batch-size 500 \
  --rejects-file artifacts/interaction-backfill-rejected.csv
```

After confirming the source timezone against a known row and resolving every
reject, use the pooled or direct database endpoint in a temporary environment
variable and apply the identical input:

```bash
read -r -s -p "Backfill DATABASE_URL: " BACKFILL_DATABASE_URL
echo
DATABASE_URL="$BACKFILL_DATABASE_URL" \
  pipenv run python -m scripts.backfill_sheet_interactions \
    --csv artifacts/logs-snapshot.csv \
    --source-id "$SHEET_ID" \
    --source-timezone Asia/Kolkata \
    --end-row "$PRE_DUAL_WRITE_ROW" \
    --batch-size 500 \
    --rejects-file artifacts/interaction-backfill-rejected.csv \
    --apply
unset BACKFILL_DATABASE_URL
```

Rerun the apply command once. The second run must report zero `imported`, all
valid rows as `skipped`, and exact
`imported + skipped + rejected == scanned` accounting.

### 6. Observe and reconcile

Keep `dual` enabled for a representative 3–7 days including peak traffic.
Do not proceed merely because row counts look similar. Export the final,
unmodified `Logs` worksheet to `artifacts/logs-final.csv`, then export the
matching application logs:

```bash
export DUAL_START='<inclusive-ISO-8601-timestamp>'
export DUAL_END='<exclusive-ISO-8601-timestamp>'
LOG_FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND textPayload:\"interaction_sink_write\" AND timestamp>=\"${DUAL_START}\" AND timestamp<\"${DUAL_END}\""
gcloud logging read "$LOG_FILTER" \
  --project "$PROJECT_ID" \
  --order=asc \
  --format='value(textPayload)' \
  > artifacts/cloud-run-dual-write.log
unset LOG_FILTER
```

Set the exact inclusive start and exclusive end timestamps for the exported
window and reconcile:

```bash
read -r -s -p "Reconciliation DATABASE_URL: " RECONCILE_DATABASE_URL
echo
DATABASE_URL="$RECONCILE_DATABASE_URL" \
  pipenv run python -m scripts.reconcile_interaction_logs \
    --csv artifacts/logs-final.csv \
    --source-id "$SHEET_ID" \
    --source-timezone Asia/Kolkata \
    --historical-end-row "$PRE_DUAL_WRITE_ROW" \
    --dual-start "$DUAL_START" \
    --dual-end "$DUAL_END" \
    --batch-size 500 \
    --application-log artifacts/cloud-run-dual-write.log \
    --rejects-file artifacts/interaction-reconcile-rejected.csv \
    --report-file artifacts/interaction-reconciliation.json
unset RECONCILE_DATABASE_URL
```

All validation gates are mandatory:

- migration-focused unit tests and disposable PostgreSQL integration tests pass;
- `alembic current` reports `20260922_0001`;
- backfill accounting is exact and a rerun is idempotent;
- no unexplained rejected rows remain;
- historical payload hashes and raw timestamps match;
- dual-write event-ID sets and all seven payload fields match, with no
  duplicate Sheet event IDs;
- application logs show PostgreSQL writes, zero write failures, acceptable
  p50/p95/max latency, and no sustained pool or timeout errors;
- the manual private-message smoke test passes in the deployed revision;
- a backup and restore drill has passed.

### 7. Backup and restore drill

Supabase Free has no automatic backups. Before PostgreSQL becomes the sole
interaction sink, either upgrade to a plan with the required backup retention
or operate a tested encrypted `pg_dump` backup outside the database project.

Create a logical backup from the direct endpoint:

```bash
read -r -s -p "Direct backup DATABASE_URL: " BACKUP_DATABASE_URL
echo
pg_dump "$BACKUP_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file=artifacts/interaction-events.dump
unset BACKUP_DATABASE_URL
```

Restore only into a disposable empty database, never over production:

```bash
read -r -s -p "Empty restore-drill DATABASE_URL: " RESTORE_DATABASE_URL
echo
pg_restore \
  --dbname="$RESTORE_DATABASE_URL" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  artifacts/interaction-events.dump
RESTORE_DATABASE_URL="$RESTORE_DATABASE_URL" pipenv run python - <<'PY'
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from telegram_bot.infrastructure.database import async_database_url

async def verify() -> None:
    engine = create_async_engine(async_database_url(os.environ["RESTORE_DATABASE_URL"]))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            count = await connection.scalar(text("SELECT count(*) FROM interaction_events"))
        assert revision == "20260922_0001"
        assert isinstance(count, int) and count >= 0
        print(f"restore drill verified: revision={revision}, interaction_events={count}")
    finally:
        await engine.dispose()

asyncio.run(verify())
PY
unset RESTORE_DATABASE_URL
```

Record the backup timestamp, encrypted storage location, checksum, restore
duration, restored revision, and row count. A dump that has not been restored
and queried does not satisfy this gate.

### 8. Cut over, observe, and roll back

Only after every gate above passes, switch the flag:

```bash
gcloud run services update "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars='INTERACTION_LOG_MODE=postgres'
```

Keep the Sheet adapter, credentials, worksheet, and rollback path intact for a
post-cutover observation window of at least 72 hours and through one expected
peak period. Monitor write failures, p50/p95/max latency, pool exhaustion,
Cloud Run errors, and interaction row growth.

If PostgreSQL writes regress, change only the flag. Use `dual` when PostgreSQL
is partly available and comparison data is useful; use `sheet` when the
database is unavailable or causing repeated timeouts:

```bash
gcloud run services update "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars='INTERACTION_LOG_MODE=dual'

# Stronger fallback:
gcloud run services update "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars='INTERACTION_LOG_MODE=sheet'
```

Do not downgrade the schema, delete PostgreSQL rows, or remove Sheet data as
part of rollback. After recovery, reconcile the affected interval before
attempting cutover again.

### 9. Legacy Sheets cleanup checklist

Cleanup is a later change, not part of initial cutover. Complete it only after
the 3–7 day dual-write window, all gates, the backup/restore drill, and the
post-cutover observation window:

- [ ] Export a final immutable Sheet archive; record checksum, row watermark,
      owner, encrypted location, and retention/deletion date.
- [ ] Run final payload reconciliation through the last Sheet-written event.
- [ ] Confirm PostgreSQL backups and a current restore drill remain valid.
- [ ] Obtain maintainer approval to retire only the interaction `Logs` sink.
- [ ] Keep Sheets for profiles, moderation warnings, and any other unmigrated
      data; those are explicitly outside this migration.
- [ ] In a separate reviewed code change, remove
      `SheetsInteractionRepository` and the interaction-log Sheet wiring only.
- [ ] Remove gspread/Google authorization dependencies only if no remaining
      application feature uses them.
- [ ] Rotate or revoke access that was used solely for the retired log sink,
      without breaking Drive or other Sheet-backed features.
- [ ] Remove the rollback flag only after the archive and recovery procedure
      are documented and accepted.
- [ ] Securely delete local CSVs, rejects, logs, reports, and dumps at the end
      of their approved retention period.

Until every checklist item is complete, the legacy Sheets interaction path is
intentionally retained.
