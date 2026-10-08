import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models import MenuItem

PROFILE = {
    "name": "Val", "email": "val@example.com", "weight_lbs": 140, "height_in": 64,
    "gender": "female", "birthdate": "2004-05-17", "activity_level": "moderate",
}


DAY = "2026-10-08"


def add_items(engine):
    """A tiny ISR menu: lunch has chicken (no allergens), a cheese pizza (Milk, Wheat, vegetarian),
    and a veggie bowl (vegan); dinner has one dish; a salad bar item is a side menu."""
    from datetime import date

    def dish(sid, name, meal, kcal, p, c, f, allergens=(), veg=False, vegan=False, rec=True):
        return MenuItem(
            source_id=sid, date=date(2026, 10, 8), hall="Illinois Street Dining Center (ISR)", meal=meal,
            name=name, kcal=kcal, protein_g=p, carbs_g=c, fat_g=f, allergens=list(allergens),
            is_vegetarian=veg or vegan, is_vegan=vegan, is_recommendable=rec,
        )

    with Session(engine) as s:
        s.add_all([
            dish("1", "Grilled Chicken", "lunch", 300, 40, 2, 12),
            dish("2", "Cheese Pizza", "lunch", 400, 15, 45, 16, ["Milk", "Wheat"], veg=True),
            dish("3", "Veggie Bowl", "lunch", 350, 12, 60, 8, vegan=True),
            dish("4", "Pasta", "dinner", 500, 18, 80, 10, ["Wheat"], veg=True),
            dish("5", "Lettuce", "salad bar", 10, 1, 2, 0, rec=False),
        ])
        s.commit()


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    add_items(engine)

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


ISR = "Illinois Street Dining Center (ISR)"


def test_halls_and_meals(client):
    assert client.get("/halls").json() == [ISR]
    assert client.get("/halls", params={"date": "2026-01-01"}).json() == []
    assert client.get("/meals", params={"hall": ISR, "date": DAY, "main_only": True}).json() == ["lunch", "dinner"]


def test_menu_items_skip_side_menus_by_default(client):
    names = {i["name"] for i in client.get("/menu-items", params={"hall": ISR, "date": DAY}).json()}
    assert names == {"Grilled Chicken", "Cheese Pizza", "Veggie Bowl", "Pasta"}
    assert "Lettuce" in {i["name"] for i in client.get("/menu-items", params={"hall": ISR, "date": DAY, "include_side_menus": True}).json()}


def test_menu_items_filtered_for_a_user(client):
    milk_free = make_user(client, allergies=["Milk"])
    names = {i["name"] for i in client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch", "user_id": milk_free}).json()}
    assert names == {"Grilled Chicken", "Veggie Bowl"}
    vegan = make_user(client, email="v@example.com", dietary_restrictions=["vegan"])
    names = {i["name"] for i in client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch", "user_id": vegan}).json()}
    assert names == {"Veggie Bowl"}
    assert client.get("/menu-items", params={"hall": ISR, "date": DAY, "user_id": 999}).status_code == 404


def test_menu_item_does_not_expose_scraper_fields(client):
    item = client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "dinner"}).json()[0]
    assert "ingredients" not in item and "source_id" not in item and item["kcal"] == 500


def test_meal_target_needs_a_goal(client):
    uid = make_user(client)
    assert client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "lunch"}).status_code == 404


def test_meal_target_adjusts_after_logging_food(client):
    uid = make_user(client)
    daily = client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"}).json()["calorie_goal"]
    before = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "dinner"}).json()
    assert before["target"]["kcal"] == pytest.approx(daily, abs=1)  # dinner is the last meal: all that's left

    lunch_items = client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch"}).json()
    chicken = next(i for i in lunch_items if i["name"] == "Grilled Chicken")
    client.post(f"/users/{uid}/food-logs", json={"item_id": chicken["id"], "servings": 2})  # 600 kcal at lunch

    after = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "dinner"}).json()
    assert after["target"]["kcal"] == pytest.approx(daily - 600, abs=1)
    assert after["remaining_day"]["kcal"] == pytest.approx(daily - 600, abs=1)


def test_meal_target_rejects_a_side_menu(client):
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    assert client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "salad bar"}).status_code == 422


def test_progress_sums_the_days_logs_and_can_undo(client):
    uid = make_user(client)
    daily = client.put(f"/users/{uid}/goal", json={"goal_type": "lose"}).json()
    items = {i["name"]: i["id"] for i in client.get("/menu-items", params={"hall": ISR, "date": DAY}).json()}
    log = client.post(f"/users/{uid}/food-logs", json={"item_id": items["Cheese Pizza"], "servings": 1.5}).json()
    client.post(f"/users/{uid}/food-logs", json={"item_id": items["Pasta"]})

    p = client.get(f"/users/{uid}/progress", params={"date": DAY}).json()
    assert p["target"]["kcal"] == daily["calorie_goal"]
    assert p["actual"]["kcal"] == pytest.approx(1.5 * 400 + 500)
    assert p["actual"]["protein_g"] == pytest.approx(1.5 * 15 + 18)
    assert p["remaining"]["kcal"] == pytest.approx(max(0, daily["calorie_goal"] - 1100))

    assert client.delete(f"/users/{uid}/food-logs/{log['id']}").status_code == 204
    p = client.get(f"/users/{uid}/progress", params={"date": DAY}).json()
    assert p["actual"]["kcal"] == pytest.approx(500)
    assert client.delete(f"/users/{uid}/food-logs/{log['id']}").status_code == 404


def test_cannot_undo_someone_elses_log(client):
    a = make_user(client)
    b = make_user(client, email="b@example.com")
    item = client.get("/menu-items", params={"hall": ISR, "date": DAY}).json()[0]["id"]
    log = client.post(f"/users/{a}/food-logs", json={"item_id": item}).json()
    assert client.delete(f"/users/{b}/food-logs/{log['id']}").status_code == 404
    assert client.delete(f"/users/{a}/food-logs/{log['id']}").status_code == 204


def test_weight_logs_and_trend(client):
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "lose"})
    client.post(f"/users/{uid}/weight-logs", json={"date": "2026-10-08", "weight_lbs": 139.4})
    client.post(f"/users/{uid}/weight-logs", json={"date": "2026-10-01", "weight_lbs": 140.2})  # older entry
    logs = client.get(f"/users/{uid}/weight-logs").json()
    assert [w["date"] for w in logs] == ["2026-10-01", "2026-10-08"]
    # current weight follows the most recent weigh-in, not the last one entered
    assert client.get(f"/users/{uid}").json()["weight_lbs"] == 139.4
    trend = client.get(f"/users/{uid}/progress", params={"date": DAY}).json()["weight_trend"]
    assert [w["weight_lbs"] for w in trend] == [140.2, 139.4]
    assert client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 0}).status_code == 422
    assert client.post("/users/999/weight-logs", json={"weight_lbs": 150}).status_code == 404
