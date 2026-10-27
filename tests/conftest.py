# SHARED FIXTURES: every test gets its own temp db

import pytest

from stemmate import create_app
from stemmate.db import get_db, init_db
from stemmate.services import auth_service

USERNAME = "facilitator1"
PASSWORD = "correct-horse-1"


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        init_db()
        auth_service.create_user(get_db(), USERNAME, PASSWORD)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    response = client.post("/api/auth/login",
                           json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    return client