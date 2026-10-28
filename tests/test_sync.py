# Sync service and routes. Requirements: FR-04, FR-05, QR-03.

import json
import sqlite3

from stemmate.db import get_db
from stemmate.services import sync_service

from .central_adapter import OfflineClient
from .helpers import full_plan, new_id, save


def completed_plan(client, **overrides):
    # Create and complete a plan (2 steps -> 3 units). Returns (plan_id, version).
    plan_id = new_id()
    version = save(client, plan_id, full_plan(**overrides)).get_json()["version"]
    done = client.post(f"/api/plans/{plan_id}/complete", json={"version": version}).get_json()
    return plan_id, done["version"]


def status_of(client, plan_id):
    return client.get(f"/api/plans/{plan_id}").get_json()["sync_status"]


def run(app, client, force=True, backoff_base=0):
    with app.app_context():
        return sync_service.run_sync(get_db(), client, force=force, backoff_base=backoff_base)


def central_rows(central_app):
    with sqlite3.connect(central_app.config["DATABASE"]) as db:
        return db.execute("SELECT plan_id, version, payload FROM committed_plan").fetchall()





# HAPPY PATH

def test_completed_plan_syncs_and_arrives_whole(app, logged_in_client, central, central_app):
    plan_id, version = completed_plan(logged_in_client)
    assert status_of(logged_in_client, plan_id) == "pending"

    assert run(app, central) == {"synced": 1, "interrupted": 0, "skipped": 0}

    assert status_of(logged_in_client, plan_id) == "synced"
    (row,) = central_rows(central_app)
    stored = json.loads(row[2])
    assert row[0] == plan_id and row[1] == version
    assert stored["header"]["title"] == "Build a simple circuit"
    assert stored["header"]["estimated_duration"] == 25
    assert [s["description"] for s in stored["steps"]] == ["Show the parts", "Connect the circuit"]


def test_drafts_are_never_synced(app, logged_in_client, central, central_app):
    save(logged_in_client, new_id(), full_plan())            # valid but never completed
    assert run(app, central) == {"synced": 0, "interrupted": 0, "skipped": 0}
    assert central_rows(central_app) == []


def test_synced_plan_is_not_sent_again(app, logged_in_client, central):
    completed_plan(logged_in_client)
    run(app, central)
    puts_before = len(central.unit_puts())
    run(app, central)
    assert len(central.unit_puts()) == puts_before





# INTERRUPTION and RESUME (QR-03) 

def test_interrupted_sync_resumes_after_the_last_confirmed_unit(app, logged_in_client, central, central_app):
    plan_id, version = completed_plan(logged_in_client) # units 0, 1, 2
    central_app.config["FAIL_AFTER_UNIT"] = 1 # link drops after unit 1

    assert run(app, central) == {"synced": 0, "interrupted": 1, "skipped": 0}
    assert status_of(logged_in_client, plan_id) == "interrupted"
    assert central_rows(central_app) == [] # nothing half-applied

    with app.app_context():
        record = get_db().execute(
            "SELECT outcome, last_step_sent FROM sync_record ORDER BY sync_id DESC LIMIT 1").fetchone()
    assert (record["outcome"], record["last_step_sent"]) == ("interrupted", 1)

    central_app.config["FAIL_AFTER_UNIT"] = None # connection is back
    central.calls.clear()
    assert run(app, central)["synced"] == 1
    assert status_of(logged_in_client, plan_id) == "synced"
    assert [p.rsplit("/", 1)[1] for p in central.unit_puts()] == ["2"]   # ONLY unit 2 was re-sent
    assert len(central_rows(central_app)) == 1


def test_no_duplicates_after_an_interruption(app, logged_in_client, central, central_app):
    plan_id, _ = completed_plan(logged_in_client)
    central_app.config["FAIL_AFTER_UNIT"] = 0
    run(app, central)
    central_app.config["FAIL_AFTER_UNIT"] = None
    run(app, central)
    run(app, central)
    assert len(central_rows(central_app)) == 1


def test_offline_marks_interrupted_and_keeps_the_plan(app, logged_in_client):
    plan_id, _ = completed_plan(logged_in_client)
    assert run(app, OfflineClient())["interrupted"] == 1
    assert status_of(logged_in_client, plan_id) == "interrupted"
    assert logged_in_client.get(f"/api/plans/{plan_id}").get_json()["title"] == "Build a simple circuit"


def test_wrong_sync_key_is_an_interruption_not_a_crash(app, logged_in_client, central_app):
    from .central_adapter import CentralTestClient
    plan_id, _ = completed_plan(logged_in_client)
    assert run(app, CentralTestClient(central_app, key="wrong"))["interrupted"] == 1
    assert status_of(logged_in_client, plan_id) == "interrupted"





# EDITING AROUND SYNC

def test_editing_after_sync_sends_the_new_version_from_unit_zero(app, logged_in_client, central, central_app):
    plan_id, version = completed_plan(logged_in_client)
    run(app, central)
    new = save(logged_in_client, plan_id, full_plan(version=version, title="Changed title")).get_json()
    assert new["sync_status"] == "pending" # must sync again
    central.calls.clear()
    run(app, central)
    assert [p.rsplit("/", 1)[1] for p in central.unit_puts()] == ["0", "1", "2"]
    (row,) = central_rows(central_app)
    assert row[1] == new["version"] and json.loads(row[2])["header"]["title"] == "Changed title"


def test_plan_is_read_only_while_syncing_then_editable_again(app, logged_in_client, central, central_app):
    plan_id, version = completed_plan(logged_in_client)
    calls = []
    original = central.put_unit

    def spy(*args, **kwargs): # runs DURING the sync
        calls.append(save(logged_in_client, plan_id, full_plan(version=version, title="mid-sync")).status_code)
        return original(*args, **kwargs)

    central.put_unit = spy
    run(app, central)
    assert set(calls) == {409} # every mid-sync edit refused
    assert save(logged_in_client, plan_id, full_plan(version=version, title="after")).status_code == 200





# CLAIMING, BACK OFF, RECOVERY

def test_a_plan_already_syncing_is_skipped(app, logged_in_client, central):
    plan_id, _ = completed_plan(logged_in_client)
    with app.app_context(), get_db() as db:
        db.execute("UPDATE session_plan SET sync_status = 'syncing' WHERE plan_id = ?", (plan_id,))
        assert sync_service.sync_plan(db, central, plan_id) == "skipped"


def test_backoff_delays_retries_but_the_button_overrides_it(app, logged_in_client):
    completed_plan(logged_in_client)
    run(app, OfflineClient())                                   # first failure
    assert run(app, OfflineClient(), force=False, backoff_base=1000) == {
        "synced": 0, "interrupted": 0, "skipped": 1}            # too soon: waits
    assert run(app, OfflineClient(), force=True)["interrupted"] == 1   # "Retry" ignores waiting


def test_stuck_syncing_plans_are_reset_at_startup(app, logged_in_client):
    plan_id, _ = completed_plan(logged_in_client)
    with app.app_context(), get_db() as db:
        db.execute("UPDATE session_plan SET sync_status = 'syncing' WHERE plan_id = ?", (plan_id,))
        assert sync_service.reset_stuck_syncs(db) == 1
    assert status_of(logged_in_client, plan_id) == "interrupted"





# ROUTES

def test_sync_run_route_syncs_and_status_route_reports(app, logged_in_client, central):
    completed_plan(logged_in_client)
    before = logged_in_client.get("/api/sync/status").get_json()
    assert before["pending"] == 1 and before["last_outcome"] is None

    assert logged_in_client.post("/api/sync/run").status_code == 202
    after = logged_in_client.get("/api/sync/status").get_json()
    assert after["synced"] == 1 and after["pending"] == 0
    assert after["last_outcome"] == "success" and after["last_attempt_at"].endswith("Z")
    assert set(after) == {"local", "pending", "syncing", "interrupted", "synced",
                          "last_attempt_at", "last_outcome"}


def test_status_counts_only_your_own_plans(app, logged_in_client, other_client):
    completed_plan(logged_in_client)
    assert other_client.get("/api/sync/status").get_json()["pending"] == 0