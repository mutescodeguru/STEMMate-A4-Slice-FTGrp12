# SIMULATED CENTRAL STORE. Requirements: FR-04, QR-03, SR-01 (AC-5)

import sqlite3

KEY = {"X-Sync-Key": "test-sync-key"}


def put_unit(client, plan_id, index, count=3, version=1, payload=None):
    return client.put(f"/central/plans/{plan_id}/units/{index}", headers=KEY,
                      json={"version": version, "unit_count": count,
                            "payload": payload or {"n": index}})


def commit(client, plan_id, count=3, version=1):
    return client.post(f"/central/plans/{plan_id}/commit", headers=KEY,
                       json={"version": version, "unit_count": count})


def progress(client, plan_id, version=1):
    return client.get(f"/central/plans/{plan_id}/progress?version={version}", headers=KEY).get_json()


def test_every_route_needs_the_sync_key(central_app):
    client = central_app.test_client()
    assert client.get("/central/plans/p/progress").status_code == 401
    wrong = client.get("/central/plans/p/progress", headers={"X-Sync-Key": "nope"})
    assert wrong.status_code == 401
    assert client.get("/central/plans/p/progress", headers=KEY).status_code == 200


def test_progress_starts_empty(central_app):
    assert progress(central_app.test_client(), "p") == {
        "last_unit_received": -1, "committed_version": None}


def test_units_advance_progress_and_repeats_are_harmless(central_app):
    client = central_app.test_client()
    assert put_unit(client, "p", 0).get_json() == {"ack": 0}
    put_unit(client, "p", 1)
    put_unit(client, "p", 1)                      # same unit again
    assert progress(client, "p")["last_unit_received"] == 1


def test_progress_only_counts_an_unbroken_run_from_zero(central_app):
    client = central_app.test_client()
    put_unit(client, "p", 0)
    put_unit(client, "p", 2)                      # unit 1 is missing
    assert progress(client, "p")["last_unit_received"] == 0


def test_commit_with_missing_units_is_409_and_lists_them(central_app):
    client = central_app.test_client()
    put_unit(client, "p", 0)
    put_unit(client, "p", 2)
    response = commit(client, "p")
    assert response.status_code == 409
    error = response.get_json()["error"]
    assert error["code"] == "MISSING_UNITS" and error["missing"] == [1]
    assert progress(client, "p")["committed_version"] is None


def test_commit_applies_everything_and_repeating_it_is_safe(central_app):
    client = central_app.test_client()
    for i in range(3):
        put_unit(client, "p", i)
    assert commit(client, "p").get_json() == {"committed_version": 1}
    assert commit(client, "p").get_json() == {"committed_version": 1}   # again: no change, no error
    with sqlite3.connect(central_app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM committed_plan").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM staged_unit").fetchone()[0] == 0   # staging cleaned


def test_failure_hook_refuses_units_after_the_limit(central_app):
    central_app.config["FAIL_AFTER_UNIT"] = 1
    client = central_app.test_client()
    assert put_unit(client, "p", 0).status_code == 200
    assert put_unit(client, "p", 1).status_code == 200
    assert put_unit(client, "p", 2).status_code == 503


def test_bad_unit_is_rejected(central_app):
    client = central_app.test_client()
    assert client.put("/central/plans/p/units/5", headers=KEY,
                      json={"version": 1, "unit_count": 3, "payload": {}}).status_code == 422
    assert client.put("/central/plans/p/units/0", headers=KEY, data="x").status_code == 422