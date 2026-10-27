-- SCHEMA: no column for pupil names (PR-01)

CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS session_plan (
    plan_id TEXT PRIMARY KEY,   -- UUID made by the browser
    owner_id INTEGER NOT NULL REFERENCES user (user_id),
    title TEXT, -- null allowed  for drafts
    level TEXT,
    estimated_duration INTEGER,
    safety_notes TEXT,
    inclusion_prompt TEXT,
    is_complete INTEGER NOT NULL DEFAULT 0 CHECK (is_complete IN (0, 1)),
    sync_status TEXT NOT NULL DEFAULT 'local'
        CHECK (sync_status IN ('local', 'pending', 'syncing', 'interrupted', 'synced')),
    version INTEGER NOT NULL DEFAULT 0,
    last_modified TEXT NOT NULL -- iso 8601 utc
);


CREATE TABLE IF NOT EXISTS plan_step (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL REFERENCES session_plan (plan_id) ON DELETE CASCADE,  --Deleting
    step_number INTEGER NOT NULL,
    description TEXT,
    duration INTEGER,
    UNIQUE (plan_id, step_number)
);


CREATE TABLE IF NOT EXISTS material (
    material_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    safety_notes TEXT
);


CREATE TABLE IF NOT EXISTS plan_material (
    plan_id TEXT NOT NULL REFERENCES session_plan (plan_id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES material (material_id),
    quantity_required INTEGER NOT NULL CHECK (quantity_required > 0),
    PRIMARY KEY (plan_id, material_id)
);


CREATE TABLE IF NOT EXISTS sync_record (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL REFERENCES session_plan (plan_id) ON DELETE CASCADE,
    attempted_at TEXT NOT NULL,
    outcome TEXT,
    last_step_sent INTEGER NOT NULL DEFAULT -1
);


-- Speeds up latest draft & list my plans
CREATE INDEX IF NOT EXISTS idx_plan_owner_modified
    ON session_plan (owner_id, is_complete, last_modified);