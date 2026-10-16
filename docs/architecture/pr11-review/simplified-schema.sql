-- DESIGN ONLY · 2026-10-17 · ENG-84
-- Proposed empty-database shape. NOT a migration, deployment script, or access policy.
-- Do not apply to an existing database. Preserve applied Alembic revisions.
-- No foreign keys. IDs are supplied by Telegram, Drive or the app.

-- One saved profile per Telegram user.
CREATE TABLE students (
    telegram_user_id BIGINT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    current_class SMALLINT CHECK (current_class IN (10, 11, 12)),
    preferred_subject TEXT CHECK (preferred_subject IN ('AI', 'CS', 'IT', 'IP')),
    created_at TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL,
    class_updated_year INTEGER NOT NULL,
    PRIMARY KEY (telegram_user_id)
);

-- One catalogue record per Drive file. Actual PDFs remain in Drive.
CREATE TABLE content_items (
    drive_file_id TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL,
    subject TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (drive_file_id)
);
CREATE INDEX ix_content_items_lookup ON content_items (level, subject, resource_type);

-- One Drive folder link per unique path.
CREATE TABLE folders (
    drive_folder_id TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (drive_folder_id)
);

-- One moderation snapshot per Telegram user and group. No profile is required.
CREATE TABLE warnings (
    telegram_user_id BIGINT NOT NULL,
    telegram_chat_id BIGINT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    warning_count INTEGER NOT NULL CHECK (warning_count >= 0),
    last_reason TEXT NOT NULL DEFAULT '',
    last_warning TIMESTAMPTZ NOT NULL,
    banned BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (telegram_user_id, telegram_chat_id)
);

-- PROPOSED: seven fields instead of twelve. Private Telegram exchanges only. One bot per database/environment. Audit log, not AI memory.
CREATE TABLE interaction_events (
    event_id UUID NOT NULL,
    telegram_update_id BIGINT UNIQUE,
    telegram_user_id BIGINT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id)
);
CREATE INDEX ix_interaction_events_occurred_at ON interaction_events (occurred_at);
CREATE INDEX ix_interaction_events_telegram_user_id ON interaction_events (telegram_user_id);
