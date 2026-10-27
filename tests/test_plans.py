# PHASE 3: save, read, restore, ownership. Requirements: FR-03, QR-02, PR-01, SR-01.

import itertools

from stemmate import create_app
from stemmate.repositories import plan_repository
from stemmate.services import plan_service

from .conftest import OTHER_USERNAME, PASSWORD, USERNAME
from .helpers import full_plan, new_id, save



# SAVING

def test_first_save_creates_version_1_as_local_draft(logged_in_client):
    plan_id = new_id()
    response = save(logged_in_client, plan_id, {"version": 0, "title": "Circuits"})
    body = response.get_json()
    assert response.status_code == 200
    assert body["plan_id"] == plan_id
    assert body["version"] == 1
    assert body["is_complete"] is False
    assert body["sync_status"] == "local"
    assert body["last_modified"].endswith("Z")


def test_version_rises_by_one_each_save(logged_in_client):
    plan_id = new_id()
    versions = []
    version = 0
    for title in ("a", "b", "c"):
        version = save(logged_in_client, plan_id, {"version": version, "title": title}).get_json()["version"]
        versions.append(version)
    assert versions == [1, 2, 3]


def test_saved_plan_can_be_read_back_with_steps_in_order(logged_in_client):
    plan_id = new_id()
    payload = full_plan(steps=[
        {"step_number": 2, "description": "Second", "duration": 5},
        {"step_number": 1, "description": "First", "duration": 10},
    ])
    save(logged_in_client, plan_id, payload)
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert [s["description"] for s in plan["steps"]] == ["First", "Second"]
    assert plan["materials"] == [{"material_id": 1, "quantity_required": 2}]
    assert plan["title"] == "Build a simple circuit"
    assert plan["is_complete"] is False


def test_save_replaces_steps_instead_of_adding(logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())
    save(logged_in_client, plan_id, {"version": 1, "steps": [{"step_number": 1, "description": "Only"}]})
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert len(plan["steps"]) == 1
    assert plan["materials"] == []
    assert plan["title"] is None





# VERSIONS

def test_stale_version_is_rejected_with_current_version(logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, {"version": 0, "title": "a"})      # now version 1
    response = save(logged_in_client, plan_id, {"version": 0, "title": "b"})
    assert response.status_code == 409
    error = response.get_json()["error"]
    assert error["code"] == "VERSION_CONFLICT"
    assert error["current_version"] == 1
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["title"] == "a"                                          # nothing was overwritten


def test_nonzero_version_for_unknown_plan_is_404(logged_in_client):
    response = save(logged_in_client, new_id(), {"version": 3, "title": "x"})
    assert response.status_code == 404





# VALIDATION

def test_invalid_plan_id_is_422(logged_in_client):
    response = logged_in_client.put("/api/plans/not-a-uuid", json={"version": 0})
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"][0]["field"] == "plan_id"


def test_unknown_fields_rejected_everywhere(logged_in_client):
    # PR-01: no learner names, photos or anything else we don't define.
    payload = full_plan(pupil_name="x")
    payload["steps"][0]["photo"] = "y"
    response = save(logged_in_client, new_id(), payload)
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "UNKNOWN_FIELD"
    assert [f["field"] for f in error["fields"]] == ["pupil_name", "steps[0].photo"]


def test_all_validation_problems_returned_at_once(logged_in_client):
    response = save(logged_in_client, new_id(),
                    {"version": 0, "title": "x" * 200, "level": "nope",
                     "steps": [{"step_number": 1, "duration": 0}]})
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert [f["field"] for f in error["fields"]] == ["title", "level", "steps[0].duration"]


def test_unknown_material_is_422(logged_in_client):
    response = save(logged_in_client, new_id(),
                    {"version": 0, "materials": [{"material_id": 999, "quantity_required": 1}]})
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"][0]["field"] == "materials[0].material_id"


def test_body_must_be_json(logged_in_client):
    response = logged_in_client.put(f"/api/plans/{new_id()}", data="title=x")
    assert response.status_code == 422





# OWNERSHIP (SR-01, AC-2) 

def test_other_users_plan_looks_like_it_does_not_exist(logged_in_client, other_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())
    assert other_client.get(f"/api/plans/{plan_id}").status_code == 404
    assert save(other_client, plan_id, {"version": 1, "title": "hijack"}).status_code == 404
    assert save(other_client, plan_id, {"version": 0, "title": "hijack"}).status_code == 404
    assert logged_in_client.get(f"/api/plans/{plan_id}").get_json()["title"] == "Build a simple circuit"


def test_list_only_shows_own_plans(logged_in_client, other_client):
    save(logged_in_client, new_id(), {"version": 0, "title": "mine"})
    save(other_client, new_id(), {"version": 0, "title": "theirs"})
    titles = [p["title"] for p in logged_in_client.get("/api/plans").get_json()]
    assert titles == ["mine"]





#  LISTS, DRAFTS, MATERIALS

def test_list_is_newest_first(logged_in_client, monkeypatch):
    clock = itertools.count(1)
    monkeypatch.setattr(plan_service, "utc_now_iso", lambda: f"2026-10-27T10:00:{next(clock):02d}.000Z")
    first, second, third = new_id(), new_id(), new_id()
    for plan_id, title in ((first, "one"), (second, "two"), (third, "three")):
        save(logged_in_client, plan_id, {"version": 0, "title": title})
    save(logged_in_client, first, {"version": 1, "title": "one again"})    # touched last
    titles = [p["title"] for p in logged_in_client.get("/api/plans").get_json()]
    assert titles == ["one again", "three", "two"]


def test_list_items_have_the_contract_fields(logged_in_client):
    save(logged_in_client, new_id(), {"version": 0, "title": "x"})
    item = logged_in_client.get("/api/plans").get_json()[0]
    assert set(item) == {"plan_id", "title", "level", "is_complete", "sync_status",
                         "version", "last_modified"}


def test_latest_draft_is_204_when_there_is_none(logged_in_client):
    assert logged_in_client.get("/api/drafts/latest").status_code == 204


def test_latest_draft_returns_the_most_recent_plan(logged_in_client, monkeypatch):
    clock = itertools.count(1)
    monkeypatch.setattr(plan_service, "utc_now_iso", lambda: f"2026-10-27T10:00:{next(clock):02d}.000Z")
    older, newer = new_id(), new_id()
    save(logged_in_client, older, {"version": 0, "title": "older"})
    save(logged_in_client, newer, {"version": 0, "title": "newer"})
    assert logged_in_client.get("/api/drafts/latest").get_json()["title"] == "newer"


def test_materials_catalogue(logged_in_client):
    materials = logged_in_client.get("/api/materials").get_json()
    assert len(materials) == 8
    assert set(materials[0]) == {"material_id", "name", "safety_notes"}





#  PERSISTENS & AUTOMACY (QR-02) 

def test_plan_survives_an_app_restart(app, logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())

    restarted = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"],
                            "SECRET_KEY": "test-secret"})          # a "new run" of the app
    client = restarted.test_client()
    client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    plan = client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["title"] == "Build a simple circuit"
    assert client.get("/api/drafts/latest").get_json()["plan_id"] == plan_id


def test_failed_save_changes_nothing(app, logged_in_client, monkeypatch):
    # The transaction rolls back everything if any part of a save fails.
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan(title="Original"))

    def explode(*args, **kwargs):
        raise RuntimeError("disk problem")

    monkeypatch.setattr(plan_repository, "replace_materials", explode)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = save(logged_in_client, plan_id, full_plan(version=1, title="Changed"))
    assert response.status_code == 500
    assert "disk problem" not in response.get_data(as_text=True)

    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["title"] == "Original"
    assert plan["version"] == 1
    assert len(plan["steps"]) == 2