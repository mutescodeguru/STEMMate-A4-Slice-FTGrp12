# SQL FOR SYNCING. Nothing here commits; the service decides when


def plans_to_sync(db):
    # Complete plans waiting to go (or that must retry), oldest first
    rows = db.execute(
        "SELECT plan_id FROM session_plan WHERE is_complete = 1"
        " AND sync_status IN ('pending', 'interrupted') ORDER BY last_modified").fetchall()
    return [row["plan_id"] for row in rows]


def claim(db, plan_id):
    # pending/interrupted -> syncing in ONE statement. Returns 1 if we got it, 0 if it wasn't claimable (someone else got there first, or it changed).
    return db.execute(
        "UPDATE session_plan SET sync_status = 'syncing' WHERE plan_id = ?"
        " AND is_complete = 1 AND sync_status IN ('pending', 'interrupted')",
        (plan_id,)).rowcount


def finish(db, plan_id, status):
    # syncing -> synced / interrupted. Only touches a plan that is still syncing.
    return db.execute(
        "UPDATE session_plan SET sync_status = ? WHERE plan_id = ? AND sync_status = 'syncing'",
        (status, plan_id)).rowcount


def reset_stuck(db):
    # After a crash a plan could stay 'syncing' forever (and be read-only).
    return db.execute(
        "UPDATE session_plan SET sync_status = 'interrupted' WHERE sync_status = 'syncing'").rowcount


def start_record(db, plan_id, now):
    return db.execute(
        "INSERT INTO sync_record (plan_id, attempted_at, outcome, last_step_sent)"
        " VALUES (?, ?, 'started', -1)", (plan_id, now)).lastrowid


def update_record(db, sync_id, last_step_sent, outcome):
    db.execute("UPDATE sync_record SET last_step_sent = ?, outcome = ? WHERE sync_id = ?",
               (last_step_sent, outcome, sync_id))


def failures_since_success(db, plan_id):
    return db.execute(
        "SELECT COUNT(*) FROM sync_record WHERE plan_id = ? AND outcome = 'interrupted'"
        " AND sync_id > COALESCE((SELECT MAX(sync_id) FROM sync_record"
        "                         WHERE plan_id = ? AND outcome = 'success'), 0)",
        (plan_id, plan_id)).fetchone()[0]


def last_attempt_time(db, plan_id):
    row = db.execute("SELECT MAX(attempted_at) AS t FROM sync_record WHERE plan_id = ?",
                     (plan_id,)).fetchone()
    return row["t"]


def status_counts(db, owner_id):
    rows = db.execute(
        "SELECT sync_status, COUNT(*) AS n FROM session_plan WHERE owner_id = ?"
        " GROUP BY sync_status", (owner_id,)).fetchall()
    return {row["sync_status"]: row["n"] for row in rows}


def last_attempt_for_owner(db, owner_id):
    return db.execute(
        "SELECT r.attempted_at, r.outcome FROM sync_record r"
        " JOIN session_plan p ON p.plan_id = r.plan_id WHERE p.owner_id = ?"
        " ORDER BY r.sync_id DESC LIMIT 1", (owner_id,)).fetchone()