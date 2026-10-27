# Phase 1: app starts, database is built correctly, errors are JSON

import sqlite3

import pytest

from stemmate.db import get_db

EXPECTED_TABLES = {"user", "session_plan", "plan_step", "material",
                   "plan_material", "sync_record"}


def test_health_returns_json(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_schema_creates_all_tables(app):
    with app.app_context():
        rows = get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    assert EXPECTED_TABLES <= {row["name"] for row in rows}


def test_init_db_can_run_twice(app):
    from stemmate.db import init_db
    with app.app_context():
        init_db()          # second run must not fail or wipe anything


def test_foreign_keys_and_wal_are_on(app):
    with app.app_context():
        db = get_db()
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_step_for_missing_plan_is_rejected(app):
    with app.app_context(), pytest.raises(sqlite3.IntegrityError):
        get_db().execute(
            "INSERT INTO plan_step (plan_id, step_number) VALUES ('nope', 1)")


def test_invalid_sync_status_is_rejected(app):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO user (username, password_hash) VALUES ('u', 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO session_plan (plan_id, owner_id, sync_status, last_modified)"
                " VALUES ('p1', 1, 'banana', '2026-10-27T00:00:00Z')")


def test_schema_has_no_learner_fields(app):
    """PR-01: no column that could hold a pupil's name or identifier."""
    banned = ("pupil", "learner", "student", "child", "photo")
    with app.app_context():
        db = get_db()
        for table in EXPECTED_TABLES:
            for col in db.execute(f"PRAGMA table_info({table})"):
                assert not any(word in col["name"].lower() for word in banned)


def test_unknown_url_returns_json_error(client):
    response = client.get("/nothing-here")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_unexpected_exception_hides_details(app):
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = app.test_client().get("/boom")
    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "SERVER_ERROR" in body
    assert "secret internal detail" not in body