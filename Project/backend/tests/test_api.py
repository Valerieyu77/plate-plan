import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app

PROFILE = {
    "name": "Val", "email": "val@example.com", "weight_lbs": 140, "height_in": 64,
    "gender": "female", "birthdate": "2004-05-17", "activity_level": "moderate",
}


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:  # the app's own startup also creates tables on the real DB; harmless locally
        yield c
    app.dependency_overrides.clear()


def make_user(client, **overrides):
    r = client.post("/users", json={**PROFILE, **overrides})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_activity_level_must_be_a_known_value(client):
    r = client.post("/users", json={**PROFILE, "activity_level": "couch potato"})
    assert r.status_code == 422


def test_set_goal_saves_and_returns_targets(client):
    uid = make_user(client)
    r = client.put(f"/users/{uid}/goal", json={"goal_type": "lose"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["calorie_goal"] and body["protein_goal_g"] and body["carb_goal_g"] and body["fat_goal_g"]
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] == body["calorie_goal"]


def test_changing_the_goal_overwrites_the_old_one(client):
    uid = make_user(client)
    lose = client.put(f"/users/{uid}/goal", json={"goal_type": "lose"}).json()["calorie_goal"]
    gain = client.put(f"/users/{uid}/goal", json={"goal_type": "gain"}).json()["calorie_goal"]
    assert gain > lose
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] == gain


def test_goal_errors(client):
    assert client.put("/users/999/goal", json={"goal_type": "lose"}).status_code == 404
    uid = make_user(client)
    assert client.put(f"/users/{uid}/goal", json={"goal_type": "bulk"}).status_code == 422
    assert client.get(f"/users/{uid}/goal").status_code == 404  # nothing saved yet
    incomplete = make_user(client, email="b@example.com", weight_lbs=None)
    r = client.put(f"/users/{incomplete}/goal", json={"goal_type": "lose"})
    assert r.status_code == 422 and "weight_lbs" in r.json()["detail"]


def test_cors_allows_the_frontend_origin(client):
    r = client.options("/users", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/users", headers={"Origin": "https://plate-plan.vercel.app", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "https://plate-plan.vercel.app"
    r = client.options("/users", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
