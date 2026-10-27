# SHARED FIXTURES: every test gets its own temp db

import pytest

from stemmate import create_app, seed_data
from stemmate.db import get_db, init_db
from stemmate.services import auth_service

USERNAME = "facilitator1"
PASSWORD = "correct-horse-1"
OTHER_USERNAME = "facilitator2"


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    # Real hashing is slow ON PURPOSE. Tests don't need that strength, so
    # use 1,000 rounds here. Production code is untouched.
    monkeypatch.setattr(auth_service, "HASH_METHOD", "pbkdf2:sha256:1000")


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        init_db()
        seed_data.seed_materials(get_db())
        auth_service.create_user(get_db(), USERNAME, PASSWORD)
        auth_service.create_user(get_db(), OTHER_USERNAME, PASSWORD)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _log_in(client, username):
    response = client.post("/api/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return client


@pytest.fixture
def logged_in_client(client):
    return _log_in(client, USERNAME)


@pytest.fixture
def other_client(app):
    # A second facilitator, logged in, with their own cookie.
    return _log_in(app.test_client(), OTHER_USERNAME)