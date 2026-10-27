# PHASE 4: completing plans and what edits do to the status. FR-03, FR-05

from stemmate.db import get_db

from .helpers import full_plan, new_id, save


def complete(client, plan_id, version):
    return client.post(f"/api/plans/{plan_id}/complete", json={"version": version})


def saved_full_plan(client):
    # Save a valid plan; returns (plan_id, version).
    plan_id = new_id()
    version = save(client, plan_id, full_plan()).get_json()["version"]
    return plan_id, version


def set_status(app, plan_id, status):
    with app.app_context():
        with get_db() as db:
            db.execute("UPDATE session_plan SET sync_status = ? WHERE plan_id = ?", (status, plan_id))





# COMPLETIMG

def test_complete_success(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    response = complete(logged_in_client, plan_id, version)
    assert response.status_code == 200
    assert response.get_json() == {"plan_id": plan_id, "version": version + 1,
                                   "is_complete": True, "sync_status": "pending"}


def test_complete_sets_estimated_duration_to_the_sum(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)         # steps: 10 + 15
    complete(logged_in_client, plan_id, version)
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["estimated_duration"] == 25
    assert plan["is_complete"] is True
    assert plan["sync_status"] == "pending"


def test_complete_with_missing_parts_lists_every_field(logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, {"version": 0, "title": "Only a title"})
    response = complete(logged_in_client, plan_id, 1)
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert [f["field"] for f in error["fields"]] == [
        "level", "safety_notes", "inclusion_prompt", "steps", "materials"]
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["is_complete"] is False and plan["version"] == 1      # nothing changed


def test_complete_stale_version_is_409(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    response = complete(logged_in_client, plan_id, version - 1)
    assert response.status_code == 409
    assert response.get_json()["error"]["current_version"] == version


def test_complete_unknown_or_foreign_plan_is_404(logged_in_client, other_client):
    plan_id, version = saved_full_plan(logged_in_client)
    assert complete(logged_in_client, new_id(), 1).status_code == 404
    assert complete(other_client, plan_id, version).status_code == 404


def test_complete_body_is_checked(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    url = f"/api/plans/{plan_id}/complete"
    assert logged_in_client.post(url, json={}).status_code == 422
    assert logged_in_client.post(url, json={"version": "1"}).status_code == 422
    extra = logged_in_client.post(url, json={"version": version, "pupil": "x"})
    assert extra.status_code == 422
    assert extra.get_json()["error"]["code"] == "UNKNOWN_FIELD"





# EDITING COMPLETED PLAN

def test_valid_edit_of_a_completed_plan_goes_back_to_pending(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    version = complete(logged_in_client, plan_id, version).get_json()["version"]
    steps = [{"step_number": 1, "description": "Longer step", "duration": 40}]
    response = save(logged_in_client, plan_id, full_plan(version=version, steps=steps))
    body = response.get_json()
    assert body["is_complete"] is True and body["sync_status"] == "pending"
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["estimated_duration"] == 40          # recalculated, not stale


def test_edit_that_breaks_a_completed_plan_makes_it_a_local_draft(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    version = complete(logged_in_client, plan_id, version).get_json()["version"]
    response = save(logged_in_client, plan_id, full_plan(version=version, inclusion_prompt=""))
    body = response.get_json()
    assert body["is_complete"] is False and body["sync_status"] == "local"
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["estimated_duration"] is None
    assert logged_in_client.get("/api/drafts/latest").get_json()["plan_id"] == plan_id


def test_editing_a_draft_keeps_it_a_draft(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)          # valid, but never completed
    body = save(logged_in_client, plan_id, full_plan(version=version, title="New title")).get_json()
    assert body["is_complete"] is False and body["sync_status"] == "local"


def test_completed_plans_are_not_offered_as_drafts(logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    complete(logged_in_client, plan_id, version)
    assert logged_in_client.get("/api/drafts/latest").status_code == 204





# SYNCING PLANS & READ ONLY

def test_save_and_complete_are_rejected_while_syncing(app, logged_in_client):
    plan_id, version = saved_full_plan(logged_in_client)
    version = complete(logged_in_client, plan_id, version).get_json()["version"]
    set_status(app, plan_id, "syncing")

    edit = save(logged_in_client, plan_id, full_plan(version=version, title="Too late"))
    assert edit.status_code == 409
    assert edit.get_json()["error"]["code"] == "PLAN_SYNCING"
    assert complete(logged_in_client, plan_id, version).get_json()["error"]["code"] == "PLAN_SYNCING"

    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["title"] == "Build a simple circuit" and plan["sync_status"] == "syncing"