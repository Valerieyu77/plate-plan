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


PASSWORD = "correct horse"


def log_in_as(client, token):
    client.headers["Authorization"] = f"Bearer {token}"


def make_user(client, password=PASSWORD, **overrides):
    """Sign up and send that user's token on every later request; returns the user id."""
    r = client.post("/auth/signup", json={**PROFILE, "password": password, **overrides})
    assert r.status_code == 201, r.text
    log_in_as(client, r.json()["token"])
    return r.json()["user"]["id"]


def test_activity_level_must_be_a_known_value(client):
    r = client.post("/auth/signup", json={**PROFILE, "password": PASSWORD, "activity_level": "couch potato"})
    assert r.status_code == 422


def test_sign_up_then_log_in(client):
    uid = make_user(client, email="Val@Example.com")
    me = client.get("/auth/me").json()
    assert me["id"] == uid and me["email"] == "val@example.com"  # stored lowercase
    assert "password" not in me and "password_hash" not in me

    r = client.post("/auth/login", json={"email": " VAL@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["id"] == uid
    log_in_as(client, r.json()["token"])
    assert client.get(f"/users/{uid}").status_code == 200


def test_sign_up_errors(client):
    make_user(client)
    r = client.post("/auth/signup", json={**PROFILE, "email": "VAL@example.com", "password": PASSWORD})
    assert r.status_code == 409  # same email in another case
    assert client.post("/auth/signup", json={**PROFILE, "email": "x@example.com", "password": "short"}).status_code == 422
    assert client.post("/auth/signup", json={**PROFILE, "email": "x@example.com", "password": "é" * 40}).status_code == 422
    assert client.post("/auth/signup", json=PROFILE).status_code == 422  # no password


def test_wrong_password_and_unknown_email_look_the_same(client):
    make_user(client)
    wrong = client.post("/auth/login", json={"email": PROFILE["email"], "password": "nope nope"})
    unknown = client.post("/auth/login", json={"email": "who@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_accounts_from_before_login_cannot_log_in(client):
    from app.models import User

    session = next(app.dependency_overrides[get_session]())
    session.add(User(name="Old", email="old@example.com"))  # no password_hash
    session.commit()
    assert client.post("/auth/login", json={"email": "old@example.com", "password": PASSWORD}).status_code == 401


def test_user_endpoints_need_the_owners_token(client):
    uid = make_user(client)
    other = make_user(client, email="b@example.com")  # now logged in as `other`
    assert client.get(f"/users/{uid}").status_code == 403
    assert client.get(f"/users/{uid}/goal").status_code == 403
    assert client.put(f"/users/{uid}/goal", json={"goal_type": "lose"}).status_code == 403
    assert client.get("/menu-items", params={"hall": ISR, "date": DAY, "user_id": uid}).status_code == 403
    assert client.get(f"/users/{other}").status_code == 200

    client.headers.pop("Authorization")
    assert client.get(f"/users/{other}").status_code == 401
    assert client.get("/auth/me").status_code == 401
    log_in_as(client, "not-a-token")
    assert client.get(f"/users/{other}").status_code == 401
    # Endpoints that don't name a user stay open
    client.headers.pop("Authorization")
    assert client.get("/menu-items", params={"hall": ISR, "date": DAY}).status_code == 200
    assert client.get("/halls").status_code == 200


def test_expired_token_is_rejected(client, monkeypatch):
    from datetime import timedelta

    from app import auth

    uid = make_user(client)
    monkeypatch.setattr(auth, "TOKEN_LIFETIME", timedelta(seconds=-1))
    log_in_as(client, auth.create_token(uid))
    assert client.get(f"/users/{uid}").status_code == 401


def test_missing_columns_are_added_to_an_existing_table():
    from sqlalchemy import inspect, text

    from app.database import create_db_and_tables

    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:  # the user table as it was before login existed
        conn.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, email VARCHAR NOT NULL, '
                          'weight_lbs FLOAT, height_in FLOAT, gender VARCHAR, birthdate DATE, activity_level VARCHAR, '
                          'allergies JSON, dietary_restrictions JSON)'))
        conn.execute(text("""INSERT INTO "user" (name, email) VALUES ('Old', 'old@example.com')"""))
    create_db_and_tables(engine)
    create_db_and_tables(engine)  # running it again changes nothing
    assert "password_hash" in {c["name"] for c in inspect(engine).get_columns("user")}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT name, password_hash FROM "user"')).one() == ("Old", None)


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
    uid = make_user(client)
    assert client.put("/users/999/goal", json={"goal_type": "lose"}).status_code == 403
    assert client.put(f"/users/{uid}/goal", json={"goal_type": "bulk"}).status_code == 422
    assert client.get(f"/users/{uid}/goal").status_code == 404  # nothing saved yet
    incomplete = make_user(client, email="b@example.com", weight_lbs=None)
    r = client.put(f"/users/{incomplete}/goal", json={"goal_type": "lose"})
    assert r.status_code == 422 and "weight_lbs" in r.json()["detail"]


def test_cors_allows_the_frontend_origin(client):
    r = client.options("/auth/signup", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/auth/signup", headers={"Origin": "https://plate-plan.vercel.app", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "https://plate-plan.vercel.app"
    r = client.options("/auth/signup", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


ISR = "Illinois Street Dining Center (ISR)"


def test_halls_and_meals(client):
    assert client.get("/halls").json() == [ISR]
    assert client.get("/halls", params={"date": "2026-01-01"}).json() == []
    assert client.get("/meals", params={"hall": ISR, "date": DAY, "main_only": True}).json() == ["lunch", "dinner"]


def test_halls_with_main_meals_come_first(client):
    from datetime import date

    session = next(app.dependency_overrides[get_session]())
    # "57 North" sorts before ISR alphabetically but only sells retail items, so it goes last
    session.add(MenuItem(source_id="r1", date=date(2026, 10, 8), hall="57 North", meal="retail", name="Latte",
                         kcal=190, protein_g=10, carbs_g=19, fat_g=7, allergens=["Milk"], is_recommendable=False))
    # "Everybody Eats" serves main meals but isn't a full dining center, so it goes after ISR
    session.add(MenuItem(source_id="e1", date=date(2026, 10, 8), hall="Everybody Eats", meal="lunch", name="Wrap",
                         kcal=450, protein_g=20, carbs_g=50, fat_g=15, allergens=[], is_recommendable=True))
    session.commit()
    assert client.get("/halls", params={"date": DAY}).json() == [ISR, "Everybody Eats", "57 North"]


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
    assert client.get("/menu-items", params={"hall": ISR, "date": DAY, "user_id": 999}).status_code == 403


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
    assert before["target"]["kcal"] == pytest.approx(daily * 0.40, abs=1)  # nothing logged: dinner's 40% of the day

    lunch_items = client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch"}).json()
    chicken = next(i for i in lunch_items if i["name"] == "Grilled Chicken")
    client.post(f"/users/{uid}/food-logs", json={"item_id": chicken["id"], "servings": 2})  # 600 kcal at lunch

    after = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "dinner"}).json()
    # lunch is logged; breakfast is not, so the rest is shared between breakfast and dinner: 0.40 / 0.65
    assert after["target"]["kcal"] == pytest.approx((daily - 600) * 0.40 / 0.65, abs=1)
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
    a_token = client.headers["Authorization"]
    item = client.get("/menu-items", params={"hall": ISR, "date": DAY}).json()[0]["id"]
    log = client.post(f"/users/{a}/food-logs", json={"item_id": item}).json()
    b = make_user(client, email="b@example.com")
    assert client.delete(f"/users/{b}/food-logs/{log['id']}").status_code == 404
    assert client.delete(f"/users/{a}/food-logs/{log['id']}").status_code == 403
    client.headers["Authorization"] = a_token
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
    assert client.post("/users/999/weight-logs", json={"weight_lbs": 150}).status_code == 403


def test_recommendation_has_the_documented_shape_and_respects_allergies(client):
    uid = make_user(client, allergies=["Milk"])
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    r = client.get("/recommendations/meals", params={
        "user_id": uid, "hall": "Illinois Street Dining Center (ISR)", "date": DAY, "meal": "lunch"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"items", "total", "target", "note"}
    assert body["items"] and "Cheese Pizza" not in [i["name"] for i in body["items"]]
    for key in ("kcal", "protein_g", "carbs_g", "fat_g"):
        assert body["total"][key] == pytest.approx(sum(i[key] for i in body["items"]))
    target = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "lunch"}).json()["target"]
    assert body["target"] == target


def test_recommendation_needs_a_goal(client):
    uid = make_user(client)
    r = client.get("/recommendations/meals", params={
        "user_id": uid, "hall": "Illinois Street Dining Center (ISR)", "date": DAY, "meal": "lunch"})
    assert r.status_code == 404



# ---------- meal picker: halls by meal, meal options ----------

def add_ike(client):
    """An extra hall with both a light lunch and a lunch (like the real Ike), and no dinner."""
    from datetime import date as d
    session = next(app.dependency_overrides[get_session]())
    for sid, meal in (("i1", "light lunch"), ("i2", "lunch"), ("i3", "breakfast")):
        session.add(MenuItem(source_id=sid, date=d(2026, 10, 8), hall="Ikenberry Dining Center (Ike)", meal=meal,
                             name=f"{meal} dish", kcal=300, protein_g=10, carbs_g=30, fat_g=10, is_recommendable=True))
    session.commit()


def test_halls_can_be_filtered_by_meal(client):
    add_ike(client)
    IKE = "Ikenberry Dining Center (Ike)"
    assert client.get("/halls", params={"date": DAY, "meal": "lunch"}).json() == [IKE, ISR]  # light lunch counts as lunch
    assert client.get("/halls", params={"date": DAY, "meal": "dinner"}).json() == [ISR]
    assert client.get("/halls", params={"date": DAY, "meal": "breakfast"}).json() == [IKE]
    assert client.get("/halls", params={"date": DAY, "meal": "light lunch"}).json() == [IKE]  # raw name: only itself
    assert client.get("/halls", params={"date": DAY, "meal": "Lunch"}).json() == [IKE, ISR]  # case-insensitive


def test_meal_options_group_light_lunch_under_lunch(client):
    add_ike(client)
    r = client.get("/meal-options", params={"hall": "Ikenberry Dining Center (Ike)", "date": DAY}).json()
    assert r == {"breakfast": ["breakfast"], "lunch": ["light lunch", "lunch"]}
    assert list(r) == ["breakfast", "lunch"]  # time-of-day order
    assert client.get("/meal-options", params={"hall": ISR, "date": DAY}).json() == {"lunch": ["lunch"], "dinner": ["dinner"]}
    assert client.get("/meal-options", params={"hall": "Nowhere", "date": DAY}).json() == {}


# ---------- the recommendation endpoint never breaks the page ----------

def _ready_user(client):
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    return uid, {"user_id": uid, "hall": ISR, "date": DAY, "meal": "lunch"}


def test_recommendation_falls_back_when_recommend_raises(client, monkeypatch):
    import app.main as main

    def boom(target, items, max_servings=3.0):
        raise ValueError("bug in someone's code")

    monkeypatch.setattr(main, "recommend", boom)
    uid, params = _ready_user(client)
    r = client.get("/recommendations/meals", params=params)
    assert r.status_code == 200
    assert "unavailable" in r.json()["note"] and r.json()["items"]


def test_recommendation_falls_back_on_a_malformed_result(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "recommend", lambda target, items, max_servings=3.0: {"nonsense": True})
    uid, params = _ready_user(client)
    r = client.get("/recommendations/meals", params=params)
    assert r.status_code == 200 and "unavailable" in r.json()["note"]


def test_a_valid_recommendation_is_passed_through_unchanged(client, monkeypatch):
    import app.main as main
    good = {"items": [{"item_id": 1, "name": "X", "servings": 1.5, "kcal": 450, "protein_g": 30, "carbs_g": 40, "fat_g": 15}],
            "total": {"kcal": 450, "protein_g": 30, "carbs_g": 40, "fat_g": 15},
            "target": {"kcal": 500, "protein_g": 35, "carbs_g": 45, "fat_g": 16}, "note": None}
    monkeypatch.setattr(main, "recommend", lambda target, items, max_servings=3.0: good)
    uid, params = _ready_user(client)
    assert client.get("/recommendations/meals", params=params).json() == good


def test_avoid_ids_are_passed_to_a_recommend_that_accepts_them(client, monkeypatch):
    import app.main as main
    seen = {}

    def with_avoid(target, items, max_servings=3.0, avoid_ids=()):
        seen["avoid"] = list(avoid_ids)
        return good_empty(target)

    monkeypatch.setattr(main, "recommend", with_avoid)
    uid, params = _ready_user(client)
    client.get("/recommendations/meals", params={**params, "avoid": "3, 7,x,9"})
    assert seen["avoid"] == [3, 7, 9]  # junk entries are ignored
    monkeypatch.setattr(main, "recommend", lambda target, items, max_servings=3.0: good_empty(target))
    assert client.get("/recommendations/meals", params={**params, "avoid": "3"}).status_code == 200  # no TypeError


def good_empty(target):
    return {"items": [], "total": {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, "target": target, "note": None}


def test_placeholder_skips_herbs_and_sauces(client):
    from datetime import date as d
    session = next(app.dependency_overrides[get_session]())
    session.add(MenuItem(source_id="h1", date=d(2026, 10, 8), hall=ISR, meal="lunch", name="Fresh Cilantro",
                         kcal=0, protein_g=0, carbs_g=0, fat_g=0, is_recommendable=True))
    session.commit()
    uid, params = _ready_user(client)
    names = [i["name"] for i in client.get("/recommendations/meals", params=params).json()["items"]]
    assert "Fresh Cilantro" not in names


# ---------- one full user journey, end to end ----------

def test_full_user_journey(client):
    """Sign up -> goal -> pick meal and hall -> target -> dishes -> recommendation -> log -> progress -> undo."""
    uid = make_user(client, allergies=["Milk"], dietary_restrictions=[])
    goal = client.put(f"/users/{uid}/goal", json={"goal_type": "lose"}).json()
    assert goal["calorie_goal"] > 1000

    assert client.get("/halls", params={"date": DAY, "meal": "lunch"}).json() == [ISR]
    assert client.get("/meal-options", params={"hall": ISR, "date": DAY}).json()["lunch"] == ["lunch"]

    target = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "lunch"}).json()
    # nothing logged yet: lunch gets its 35% of the day
    assert target["target"]["kcal"] == pytest.approx(goal["calorie_goal"] * 0.35, abs=1)

    dishes = client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch", "user_id": uid}).json()
    names = {d["name"] for d in dishes}
    assert "Cheese Pizza" not in names and "Grilled Chicken" in names  # Milk allergy respected

    rec = client.get("/recommendations/meals", params={"user_id": uid, "hall": ISR, "date": DAY, "meal": "lunch"}).json()
    assert rec["items"] and rec["target"] == target["target"]
    assert all(line["name"] in names for line in rec["items"])  # only dishes this user may eat

    first = rec["items"][0]
    log = client.post(f"/users/{uid}/food-logs", json={"item_id": first["item_id"], "servings": first["servings"]}).json()
    after = client.get(f"/users/{uid}/meal-target", params={"date": DAY, "meal": "lunch"}).json()
    assert after["consumed_this_meal"]["kcal"] == pytest.approx(first["kcal"], abs=1)
    assert after["target"]["kcal"] < target["target"]["kcal"]

    progress = client.get(f"/users/{uid}/progress", params={"date": DAY}).json()
    assert progress["actual"]["kcal"] == pytest.approx(first["kcal"], abs=1)

    client.post(f"/users/{uid}/weight-logs", json={"date": DAY, "weight_lbs": 139.0})
    assert client.get(f"/users/{uid}/progress", params={"date": DAY}).json()["weight_trend"][-1]["weight_lbs"] == 139.0

    assert client.delete(f"/users/{uid}/food-logs/{log['id']}").status_code == 204
    assert client.get(f"/users/{uid}/progress", params={"date": DAY}).json()["actual"]["kcal"] == 0



# ---------- today's best picks across halls ----------

PAR = "Pennsylvania Avenue Dining Hall (PAR)"


def add_poor_lunch_hall(client):
    """A hall whose only lunch dish is one huge pizza: it can't build a plate that fits a ~600 kcal lunch."""
    from datetime import date as d
    session = next(app.dependency_overrides[get_session]())
    session.add(MenuItem(source_id="p1", date=d(2026, 10, 8), hall=PAR, meal="lunch", name="Mega Pizza", category="Entrees",
                         kcal=900, protein_g=20, carbs_g=100, fat_g=40, allergens=[], is_recommendable=True))
    session.commit()


def test_hall_picks_rank_halls_by_how_well_a_plate_fits(client):
    add_poor_lunch_hall(client)
    uid = make_user(client, allergies=["Milk"])
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    r = client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "lunch"}).json()
    halls = [h["hall"] for h in r["halls"]]
    assert halls == [ISR, PAR] and r["best_match"] == ISR
    scores = [h["match"] for h in r["halls"]]
    assert scores == sorted(scores, reverse=True) and scores[0] > scores[1]
    isr = r["halls"][0]
    assert "Cheese Pizza" not in [i["name"] for i in isr["tray"]["items"]]  # Milk allergy respected
    assert isr["high_protein"]["items"] and isr["high_protein"]["protein_share"] > 0
    assert r["best_protein"] in halls and r["target"]["kcal"] > 0


def test_hall_picks_only_lists_halls_that_serve_the_meal(client):
    add_poor_lunch_hall(client)
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    r = client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "dinner"}).json()
    assert [h["hall"] for h in r["halls"]] == [ISR]  # PAR has no dinner in this test data


def test_hall_picks_with_nothing_to_show_and_bad_requests(client):
    uid = make_user(client)
    assert client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "lunch"}).status_code == 404  # no goal yet
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    assert client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "snack"}).status_code == 422
    r = client.get(f"/users/{uid}/hall-picks", params={"date": "2026-12-01", "meal": "lunch"}).json()
    assert r["halls"] == [] and r["best_match"] is None and r["best_protein"] is None
    assert client.get("/users/999/hall-picks", params={"date": DAY, "meal": "lunch"}).status_code == 403


def test_hall_picks_follow_what_was_already_logged(client):
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    before = client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "lunch"}).json()["target"]["kcal"]
    item = client.get("/menu-items", params={"hall": ISR, "date": DAY, "meal": "lunch"}).json()[0]["id"]
    client.post(f"/users/{uid}/food-logs", json={"item_id": item, "servings": 1})
    after = client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "lunch"}).json()["target"]["kcal"]
    assert after < before


def test_best_protein_never_names_a_hall_without_a_high_protein_plate(client, monkeypatch):
    import app.main as main
    real = main.recommend

    def no_protein_plate(target, items, **kwargs):
        # the high-protein request has a 40%-protein split; make it come back empty for every hall
        if target["protein_g"] * 4 >= 0.39 * target["kcal"]:
            return {"items": [], "total": {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, "target": target, "note": "none"}
        return real(target, items, **kwargs)

    monkeypatch.setattr(main, "recommend", no_protein_plate)
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    r = client.get(f"/users/{uid}/hall-picks", params={"date": DAY, "meal": "lunch"}).json()
    assert r["halls"] and r["best_match"]  # the hall comparison still works
    assert r["best_protein"] is None
