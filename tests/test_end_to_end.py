# One facilitator's whole journey through the HTTP API (the demo as a test).
# Requirements: FR-03, FR-04, FR-05, QR-02, QR-03.

from .helpers import full_plan, new_id, save


def test_whole_journey_with_an_outage_in_the_middle(app, logged_in_client, central, central_app):
    # 1. Autosave a rough draft, then close and come back (QR-02).
    plan_id = new_id()
    first = save(logged_in_client, plan_id, {"version": 0, "title": "Draft"}).get_json()
    assert first["sync_status"] == "local"
    restored = logged_in_client.get("/api/drafts/latest")
    assert restored.status_code == 200 and restored.get_json()["title"] == "Draft"

    # 2. Finish the plan and complete it (FR-03).
    saved = save(logged_in_client, plan_id, full_plan(version=first["version"])).get_json()
    done = logged_in_client.post(f"/api/plans/{plan_id}/complete",
                                 json={"version": saved["version"]}).get_json()
    assert done["is_complete"] is True and done["sync_status"] == "pending"
    assert logged_in_client.get("/api/sync/status").get_json()["pending"] == 1

    # 3. The link drops mid-sync (QR-03)...
    central_app.config["FAIL_AFTER_UNIT"] = 1
    logged_in_client.post("/api/sync/run")
    status = logged_in_client.get("/api/sync/status").get_json()
    assert status["interrupted"] == 1 and status["last_outcome"] == "interrupted"

    # 4. ...it comes back, the sync resumes, and the plan arrives once (FR-04, FR-05).
    central_app.config["FAIL_AFTER_UNIT"] = None
    logged_in_client.post("/api/sync/run")
    status = logged_in_client.get("/api/sync/status").get_json()
    assert status["synced"] == 1 and status["interrupted"] == 0
    assert logged_in_client.get(f"/api/plans/{plan_id}").get_json()["sync_status"] == "synced"


def test_home_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200 and b"STEMMate" in response.data