# PHASE 4: the 50 MB budget. Requirement: QR-01

from stemmate.services import storage_service

from .helpers import full_plan, new_id, save


def test_storage_endpoint_shape(logged_in_client):
    body = logged_in_client.get("/api/storage").get_json()
    assert set(body) == {"used_bytes", "limit_bytes", "percent"}
    assert body["limit_bytes"] == 50 * 1024 * 1024
    assert body["used_bytes"] > 0   # the empty schema already takes space
    assert isinstance(body["percent"], float)


def test_usage_math_is_pure():
    assert storage_service.usage("does-not-exist.db", 1000) == {
        "used_bytes": 0, "limit_bytes": 1000, "percent": 0.0}


def test_save_is_refused_when_the_limit_would_be_passed(app, logged_in_client):
    plan_id = new_id()
    first = save(logged_in_client, plan_id, full_plan(title="Original"))
    assert first.status_code == 200

    used = logged_in_client.get("/api/storage").get_json()["used_bytes"]
    app.config["STORAGE_LIMIT_BYTES"] = used + 10           # almost full

    response = save(logged_in_client, plan_id, full_plan(version=1, title="Changed"))
    assert response.status_code == 507
    assert response.get_json()["error"]["code"] == "STORAGE_LIMIT"
    assert "full" in response.get_json()["error"]["message"]

    # Existing data is untouched
    plan = logged_in_client.get(f"/api/plans/{plan_id}").get_json()
    assert plan["title"] == "Original" and plan["version"] == 1


def test_new_plans_are_refused_too_and_nothing_is_created(app, logged_in_client):
    app.config["STORAGE_LIMIT_BYTES"] = 1
    assert save(logged_in_client, new_id(), {"version": 0, "title": "x"}).status_code == 507
    assert logged_in_client.get("/api/plans").get_json() == []


def test_reading_still_works_when_storage_is_full(app, logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())
    app.config["STORAGE_LIMIT_BYTES"] = 1
    assert logged_in_client.get(f"/api/plans/{plan_id}").status_code == 200
    assert logged_in_client.get("/api/drafts/latest").status_code == 200