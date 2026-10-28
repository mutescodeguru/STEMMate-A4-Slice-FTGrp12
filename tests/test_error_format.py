# EVERY FAILURE uses P1's one JSON error shape and never leaks internals.
# Requirements: SR-01, PR-01, QR-01, QR-02.

import pytest

from stemmate.services import plan_service

from .helpers import full_plan, new_id, save


def assert_clean_error(response, status, code=None):
    assert response.status_code == status
    body = response.get_json()
    assert set(body) == {"error"}
    assert body["error"]["code"] and body["error"]["message"]
    if code:
        assert body["error"]["code"] == code
    text = response.get_data(as_text=True)
    for leak in ("Traceback", "sqlite3", "SELECT ", ".py"):
        assert leak not in text


def test_401_when_not_logged_in(client):
    assert_clean_error(client.get("/api/plans"), 401)


def test_404_unknown_plan_and_other_peoples_plans(logged_in_client, other_client):
    assert_clean_error(logged_in_client.get(f"/api/plans/{new_id()}"), 404)
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())
    assert_clean_error(other_client.get(f"/api/plans/{plan_id}"), 404)


def test_404_and_405_for_bad_urls_are_json_too(logged_in_client):
    assert_clean_error(logged_in_client.get("/api/nothing-here"), 404)
    assert_clean_error(logged_in_client.delete("/api/plans"), 405)


def test_409_stale_version(logged_in_client):
    plan_id = new_id()
    save(logged_in_client, plan_id, full_plan())
    assert_clean_error(save(logged_in_client, plan_id, full_plan(version=0)), 409)


def test_422_lists_each_bad_field(logged_in_client):
    response = save(logged_in_client, new_id(), {"version": 0, "title": "", "surprise": 1})
    assert_clean_error(response, 422)
    assert response.get_json()["error"]["fields"]


def test_422_for_non_json_body(logged_in_client):
    response = logged_in_client.put(f"/api/plans/{new_id()}", data="not json")
    assert_clean_error(response, 422)


def test_500_hides_the_real_cause(app, logged_in_client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail sqlite3 Traceback")
    monkeypatch.setattr(plan_service, "list_plans", boom)
    response = logged_in_client.get("/api/plans")
    assert_clean_error(response, 500, "SERVER_ERROR")
    assert "secret internal detail" not in response.get_data(as_text=True)