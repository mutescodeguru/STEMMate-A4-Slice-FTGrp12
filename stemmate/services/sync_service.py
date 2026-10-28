# Resumable, repeat-safe sync of completed plans to the central store (FR-04, FR-05, QR-03; P1's ADR-003).

# A plan is sent as small UNITS: unit 0 = the plan header with its materials, units 1..n = one step each. After an interruption we ask the central store
# which units it already has and continue from the next one.

import threading
import time
from datetime import datetime, timezone

from ..repositories import plan_repository, sync_repository
from ..timeutil import utc_now_iso
from .central_client import CentralError, HttpCentralClient

MAX_BACKOFF_SECONDS = 300


def build_units(db, plan_id):
    # Return (version, [unit0_header, unit1_step, ...]) for a plan
    row = plan_repository.get_row(db, plan_id)
    header = {
        "title": row["title"], "level": row["level"],
        "estimated_duration": row["estimated_duration"],
        "safety_notes": row["safety_notes"], "inclusion_prompt": row["inclusion_prompt"],
        "materials": [dict(m) for m in plan_repository.get_materials(db, plan_id)],
    }
    steps = [dict(s) for s in plan_repository.get_steps(db, plan_id)]
    return row["version"], [header] + steps


def _finish(db, plan_id, sync_id, status, outcome, last_step_sent):
    with db:
        sync_repository.finish(db, plan_id, status)
        sync_repository.update_record(db, sync_id, last_step_sent, outcome)


def sync_plan(db, client, plan_id):
    # Try to sync ONE plan. Returns "synced", "interrupted" or "skipped"
    with db:
        if sync_repository.claim(db, plan_id) == 0:
            return "skipped"                      # not pending/interrupted, or already claimed
        sync_id = sync_repository.start_record(db, plan_id, utc_now_iso())

    last_sent = -1
    try:
        version, units = build_units(db, plan_id)
        count = len(units)
        progress = client.progress(plan_id, version)
        if progress.get("committed_version") != version:
            last_sent = progress["last_unit_received"]
            for index in range(last_sent + 1, count): # resume, do not restart
                client.put_unit(plan_id, index, version, count, units[index])
                last_sent = index
                with db:
                    sync_repository.update_record(db, sync_id, last_sent, "started")
            client.commit(plan_id, version, count)
        _finish(db, plan_id, sync_id, "synced", "success", last_sent)
        return "synced"
    except Exception as err:
        _finish(db, plan_id, sync_id, "interrupted", "interrupted", last_sent)
        if not isinstance(err, CentralError):
            raise # a real bug
        return "interrupted"


def _parse(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _is_due(db, plan_id, backoff_base):
    # Exponential back-off: after n failures wait base * 2^n seconds (max 300)
    failures = sync_repository.failures_since_success(db, plan_id)
    if failures == 0:
        return True
    last = sync_repository.last_attempt_time(db, plan_id)
    wait = min(backoff_base * 2 ** failures, MAX_BACKOFF_SECONDS)
    elapsed = (datetime.now(timezone.utc) - _parse(last)).total_seconds()
    return elapsed >= wait


def run_sync(db, client, force=False, backoff_base=5):
    # Sync every waiting plan. `force=True` (the Sync now button) ignores back-off
    summary = {"synced": 0, "interrupted": 0, "skipped": 0}
    for plan_id in sync_repository.plans_to_sync(db):
        if not force and not _is_due(db, plan_id, backoff_base):
            summary["skipped"] += 1
            continue
        summary[sync_plan(db, client, plan_id)] += 1
    return summary


def reset_stuck_syncs(db):
    # Call at start-up: a crash mid-sync must not leave a plan read-only forever
    with db:
        return sync_repository.reset_stuck(db)


def sync_status(db, owner_id):
    counts = sync_repository.status_counts(db, owner_id)
    last = sync_repository.last_attempt_for_owner(db, owner_id)
    result = {name: counts.get(name, 0)
              for name in ("local", "pending", "syncing", "interrupted", "synced")}
    result["last_attempt_at"] = last["attempted_at"] if last else None
    result["last_outcome"] = last["outcome"] if last else None
    return result


def make_client(app):
    # Tests put a fake in app.config["CENTRAL_CLIENT"]; real runs use HTTP
    return app.config.get("CENTRAL_CLIENT") or HttpCentralClient(
        app.config["CENTRAL_URL"], app.config["SYNC_KEY"])


def run_in_app(app, force):
    # Run one sync pass with its own database connection (safe in a thread)
    from ..db import get_db
    with app.app_context():
        return run_sync(get_db(), make_client(app), force=force,
                        backoff_base=app.config["SYNC_BACKOFF_BASE_SECONDS"])


def start_scheduler(app):
    # Background loop: reset stuck plans once, then sync every N seconds
    from ..db import get_db
    with app.app_context():
        reset_stuck_syncs(get_db())

    def loop():
        while True:
            time.sleep(app.config["SYNC_INTERVAL_SECONDS"])
            try:
                run_in_app(app, force=False)
            except Exception:
                app.logger.exception("Background sync failed")

    thread = threading.Thread(target=loop, daemon=True, name="sync-scheduler")
    thread.start()
    return thread