from fastapi.testclient import TestClient
from main import app

def test_authenticated_mutation_requires_allowed_origin():
    client = TestClient(app)
    response = client.post("/auth/logout", cookies={"session_token": "opaque"})
    assert response.status_code == 403
    response = client.post("/auth/logout", cookies={"session_token": "opaque"}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200

def test_hostile_origin_is_rejected_but_safe_get_is_allowed():
    client = TestClient(app)
    response = client.post("/auth/logout", cookies={"session_token": "opaque"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    response = client.get("/health", cookies={"session_token": "opaque"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 200

def test_matching_referer_is_accepted():
    client = TestClient(app)
    response = client.post("/auth/logout", cookies={"session_token": "opaque"}, headers={"Referer": "http://localhost:5173/settings"})
    assert response.status_code == 200
