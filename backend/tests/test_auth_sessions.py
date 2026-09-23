import models
from tests.helpers import create_user

def test_login_uses_opaque_server_session_and_logout_invalidates(client, db):
    response = client.post("/auth/register", json={"email": " User@Example.com ", "password": "password123"})
    assert response.status_code == 200
    login = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    cookie = login.cookies.get("session_token")
    assert cookie and len(cookie) > 20
    row = db.query(models.Session).one()
    assert row.token_hash != cookie
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401

def test_registration_rejects_short_password(client):
    response = client.post("/auth/register", json={"email": "short@example.com", "password": "short"})
    assert response.status_code == 400
