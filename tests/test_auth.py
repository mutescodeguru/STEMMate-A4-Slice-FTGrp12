# PHASE 2: login, logout, session rules, hashing. Requirement: SR-01
# 17 tests that prove the login rules, each tagged to a requirement

import re
import time

import pytest

from stemmate.db import get_db
from stemmate.services import auth_service
from stemmate.validators import unknown_fields, validate_login

from .conftest import PASSWORD, USERNAME


def login(client, username=USERNAME, password=PASSWORD):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password})


# LOGIN AREA:

def test_login_success_returns_user(client):
    response = login(client)
    assert response.status_code == 200
    assert response.get_json()["username"] == USERNAME


def test_wrong_password_and_unknown_user_look_identical(client):
    # SR-01: the same message so attackers can't discover usernames
    wrong_pw = login(client, password="wrong-password")
    no_user = login(client, username="nobody-here")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.get_json() == no_user.get_json()
    assert wrong_pw.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_missing_fields_lists_each_field(client):
    response = client.post("/api/auth/login", json={"username": ""})
    assert response.status_code == 422
    fields = {f["field"] for f in response.get_json()["error"]["fields"]}
    assert fields == {"username", "password"}


def test_login_rejects_unknown_field(client):
    # PR-01: fields outside the allowlist are refused
    response = client.post("/api/auth/login", json={
        "username": USERNAME, "password": PASSWORD, "pupil_name": "x"})
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_login_rejects_non_json_body(client):
    response = client.post("/api/auth/login", data="username=a&password=b")
    assert response.status_code == 422




# SESSION BEHAVIOUR:

def test_me_requires_login(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_me_after_login(logged_in_client):
    response = logged_in_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["username"] == USERNAME


def test_logout_ends_session(logged_in_client):
    assert logged_in_client.post("/api/auth/logout").status_code == 204
    assert logged_in_client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_401(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_cookie_is_httponly_and_samesite_strict(client):
    cookie = login(client).headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert re.search(r"SameSite=Strict", cookie)


def test_session_expires_when_idle(app):
    app.config["PERMANENT_SESSION_LIFETIME"] = __import__("datetime").timedelta(seconds=1)
    client = app.test_client()
    assert login(client).status_code == 200
    time.sleep(2)
    assert client.get("/api/auth/me").status_code == 401


def test_every_api_route_except_login_requires_a_session(app):
    # AC-1: a safety net that also covers routes added in later phases
    client = app.test_client()
    checked = 0
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.endpoint == "auth.login":
            continue
        url = re.sub(r"<[^>]+>", "x", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            response = client.open(url, method=method)
            assert response.status_code == 401, f"{method} {url} is not protected"
            checked += 1
    assert checked >= 2




# PASSWORDS AND ACCOUNTS

def test_password_is_stored_as_salted_hash(app):
    with app.app_context():
        row = get_db().execute(
            "SELECT password_hash FROM user WHERE username = ?", (USERNAME,)).fetchone()
    assert row["password_hash"] != PASSWORD
    assert row["password_hash"].startswith("pbkdf2:sha256")


def test_same_password_gets_different_hashes(app):
    with app.app_context():
        db = get_db()
        auth_service.create_user(db, "user-a", "samePassword1")
        auth_service.create_user(db, "user-b", "samePassword1")
        hashes = [r[0] for r in db.execute(
            "SELECT password_hash FROM user WHERE username IN ('user-a','user-b')")]
    assert hashes[0] != hashes[1]  # different salts


def test_create_user_rejects_duplicate_and_weak_input(app):
    with app.app_context():
        db = get_db()
        with pytest.raises(ValueError, match="already exists"):
            auth_service.create_user(db, USERNAME, "another-password")
        with pytest.raises(ValueError, match="8 characters"):
            auth_service.create_user(db, "short-pw-user", "abc")
        with pytest.raises(ValueError, match="3 characters"):
            auth_service.create_user(db, "ab", "long-enough-pw")




# PURE VALIDATORS (no app needed) 

def test_validate_login_pure():
    assert validate_login({"username": "a", "password": "b"}) == []
    assert len(validate_login({})) == 2
    assert len(validate_login({"username": 5, "password": "  "})) == 2


def test_unknown_fields_pure():
    assert unknown_fields({"a": 1, "b": 2, "c": 3}, ("a",)) == ["b", "c"]