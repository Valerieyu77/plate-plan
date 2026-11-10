"""Quick-add food, deleting weigh-ins, editing the profile, changing the password, deleting the account."""

import pytest
from sqlmodel import select

from app.database import get_session
from app.main import _today, app
from app.models import FoodLog, Goal, User, WeightLog, WorkoutLog
from tests.test_api import DAY, PASSWORD, PROFILE, client, log_in_as, make_user  # noqa: F401 (client is a fixture)


def with_goal(client, **kw):
    uid = make_user(client, **kw)
    assert client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"}).status_code == 200
    return uid


# ---------- quick add ----------

def test_quick_add_counts_everywhere_a_menu_dish_does(client):
    uid = with_goal(client)
    r = client.post(f"/users/{uid}/food-logs", json={"name": "Starbucks latte", "kcal": 190, "protein_g": 12, "date": DAY})
    assert r.status_code == 201, r.text
    log = r.json()
    assert log["meal"] == "snack" and log["item_id"] is None and log["name"] == "Starbucks latte" and log["kcal"] == 190

    client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": 1})  # 300 kcal chicken at lunch on DAY
    progress = client.get(f"/users/{uid}/progress?date={DAY}").json()
    assert progress["actual"]["kcal"] == 490 and progress["actual"]["protein_g"] == 52
    assert client.get(f"/users/{uid}/energy?date={DAY}").json()["eaten"] == 490
    assert len(client.get(f"/users/{uid}/food-logs?date={DAY}").json()) == 2


def test_a_snack_comes_off_the_day_without_taking_a_meal_slot(client):
    uid = with_goal(client)
    before = client.get(f"/users/{uid}/meal-target?date={DAY}&meal=dinner").json()
    client.post(f"/users/{uid}/food-logs", json={"name": "Chips", "kcal": 300, "date": DAY})
    after = client.get(f"/users/{uid}/meal-target?date={DAY}&meal=dinner").json()
    # Dinner's share of what is left: (day - 300) x 40%, still shared with breakfast and lunch to come
    assert after["meal_budget"]["kcal"] == pytest.approx((before["daily_target"]["kcal"] - 300) * 0.40, abs=1)


def test_quick_add_into_a_meal_and_without_macros(client):
    uid = with_goal(client)
    r = client.post(f"/users/{uid}/food-logs", json={"name": "Chipotle bowl", "kcal": 850, "meal": "Lunch", "date": DAY})
    assert r.status_code == 201 and r.json()["meal"] == "lunch" and r.json()["protein_g"] is None
    lunch = client.get(f"/users/{uid}/meal-target?date={DAY}&meal=lunch").json()
    assert lunch["consumed_this_meal"]["kcal"] == 850 and lunch["consumed_this_meal"]["protein_g"] == 0
    assert client.delete(f"/users/{uid}/food-logs/{r.json()['id']}").status_code == 204


@pytest.mark.parametrize("body", [
    {"name": "Pizza"},                                  # no kcal
    {"kcal": 300},                                      # no name
    {"name": "  ", "kcal": 300},
    {"name": "Pizza", "kcal": 0},
    {"name": "Pizza", "kcal": 9000},
    {"name": "Pizza", "kcal": 300, "meal": "brunch"},
    {"item_id": 1, "name": "Pizza", "kcal": 300},       # both kinds at once
    {},
])
def test_bad_quick_adds_are_refused(client, body):
    uid = make_user(client)
    assert client.post(f"/users/{uid}/food-logs", json=body).status_code == 422


# ---------- deleting a weigh-in ----------

def test_deleting_a_typo_weigh_in_puts_the_weight_and_plan_back(client):
    from datetime import timedelta

    uid = make_user(client)  # 140 lb
    goal = {"target_weight_lbs": 130, "target_date": str(_today() + timedelta(days=120))}
    assert client.put(f"/users/{uid}/goal", json=goal).status_code == 200
    planned = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    good = client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 139, "date": str(_today())}).json()
    after_good = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    typo = client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 193, "date": str(_today())}).json()
    assert client.get(f"/users/{uid}").json()["weight_lbs"] == 193

    assert client.delete(f"/users/{uid}/weight-logs/{typo['id']}").status_code == 204
    assert client.get(f"/users/{uid}").json()["weight_lbs"] == 139
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] == after_good
    assert [w["weight_lbs"] for w in client.get(f"/users/{uid}/weight-logs").json()] == [139]

    # Removing the last one goes back to the start weight
    assert client.delete(f"/users/{uid}/weight-logs/{good['id']}").status_code == 204
    assert client.get(f"/users/{uid}").json()["weight_lbs"] == 140
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] == pytest.approx(planned, abs=2)
    assert client.delete(f"/users/{uid}/weight-logs/{good['id']}").status_code == 404


def test_only_your_own_weigh_ins_can_be_deleted(client):
    uid = make_user(client)
    log = client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 139}).json()
    other = make_user(client, email="other@example.com")
    assert client.delete(f"/users/{uid}/weight-logs/{log['id']}").status_code == 403
    assert client.delete(f"/users/{other}/weight-logs/{log['id']}").status_code == 404


# ---------- editing the profile ----------

def test_editing_allergies_changes_the_menu_right_away(client):
    uid = make_user(client)
    menu = lambda: {i["name"] for i in client.get(
        f"/menu-items?hall=Illinois Street Dining Center (ISR)&date={DAY}&meal=lunch&user_id={uid}").json()}
    assert "Cheese Pizza" in menu()
    r = client.patch(f"/users/{uid}", json={"allergies": ["Milk", " milk ", ""]})
    assert r.status_code == 200 and r.json()["allergies"] == ["Milk"]
    assert "Cheese Pizza" not in menu()
    client.patch(f"/users/{uid}", json={"allergies": [], "dietary_restrictions": ["vegan"]})
    assert menu() == {"Veggie Bowl"}


def test_editing_body_or_activity_recalculates_the_goal(client):
    uid = with_goal(client)
    before = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    r = client.patch(f"/users/{uid}", json={"activity_level": "very_active", "name": "Valerie"})
    assert r.status_code == 200 and r.json()["name"] == "Valerie" and r.json()["email"] == PROFILE["email"]
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] > before
    client.patch(f"/users/{uid}", json={"height_in": 70})
    assert client.get(f"/users/{uid}").json()["height_in"] == 70


@pytest.mark.parametrize("body", [
    {"activity_level": "couch potato"}, {"height_in": 0}, {"meals": []}, {"name": ""}, {"activity_level": None},
])
def test_bad_profile_edits_are_refused(client, body):
    uid = make_user(client)
    assert client.patch(f"/users/{uid}", json=body).status_code == 422


def test_the_profile_edit_ignores_email_and_weight(client):
    uid = make_user(client)
    me = client.patch(f"/users/{uid}", json={"email": "new@example.com", "weight_lbs": 100}).json()
    assert me["email"] == PROFILE["email"] and me["weight_lbs"] == 140


# ---------- password and account ----------

def test_change_password(client):
    make_user(client)
    wrong = client.post("/auth/change-password", json={"current_password": "nope nope", "new_password": "a brand new one"})
    assert wrong.status_code == 401
    short = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"})
    assert short.status_code == 422
    ok = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "a brand new one"})
    assert ok.status_code == 204
    assert client.post("/auth/login", json={"email": PROFILE["email"], "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": PROFILE["email"], "password": "a brand new one"}).status_code == 200


def test_change_password_needs_a_login(client):
    r = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "a brand new one"})
    assert r.status_code == 401


def test_deleting_the_account_removes_everything(client):
    uid = with_goal(client)
    client.post(f"/users/{uid}/food-logs", json={"item_id": 1})
    client.post(f"/users/{uid}/food-logs", json={"name": "Latte", "kcal": 190})
    client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 139})
    client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "bike", "minutes": 20})

    assert client.request("DELETE", f"/users/{uid}", json={"password": "wrong one"}).status_code == 401
    assert client.request("DELETE", f"/users/{uid}", json={"password": PASSWORD}).status_code == 204

    session = next(app.dependency_overrides[get_session]())
    assert session.get(User, uid) is None and session.get(Goal, uid) is None
    for table in (FoodLog, WeightLog, WorkoutLog):
        assert session.exec(select(table).where(table.user_id == uid)).all() == []
    assert client.get("/auth/me").status_code == 401  # the old token no longer finds an account
    assert client.post("/auth/login", json={"email": PROFILE["email"], "password": PASSWORD}).status_code == 401


def test_someone_else_cant_delete_your_account(client):
    uid = make_user(client)
    make_user(client, email="other@example.com")
    assert client.request("DELETE", f"/users/{uid}", json={"password": PASSWORD}).status_code == 403


# ---------- favorite halls ----------

ISR = "Illinois Street Dining Center (ISR)"
IKE = "Ikenberry Dining Center (Ike)"


def test_star_and_unstar_halls(client):
    uid = make_user(client)
    assert client.get(f"/users/{uid}").json()["favorite_halls"] is None

    r = client.patch(f"/users/{uid}", json={"favorite_halls": [f"  {ISR} ", IKE, ISR, ""]})
    assert r.status_code == 200, r.text
    assert r.json()["favorite_halls"] == [ISR, IKE]  # trimmed, blanks and repeats dropped, order kept
    assert client.get("/auth/me").json()["favorite_halls"] == [ISR, IKE]

    # Editing something else leaves the stars alone
    client.patch(f"/users/{uid}", json={"name": "Renamed"})
    assert client.get(f"/users/{uid}").json()["favorite_halls"] == [ISR, IKE]

    assert client.patch(f"/users/{uid}", json={"favorite_halls": []}).json()["favorite_halls"] == []


def test_too_many_favorite_halls_is_refused(client):
    uid = make_user(client)
    r = client.patch(f"/users/{uid}", json={"favorite_halls": [f"Hall {i}" for i in range(11)]})
    assert r.status_code == 422


def test_favorite_halls_column_is_added_to_an_old_database():
    from sqlalchemy import create_engine, inspect, text
    from sqlmodel.pool import StaticPool
    from app.database import create_db_and_tables

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:  # a user table from before favorites existed
        conn.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, email VARCHAR NOT NULL)'))
    create_db_and_tables(engine)
    assert "favorite_halls" in {c["name"] for c in inspect(engine).get_columns("user")}


# ---------- the day's food log ----------

def test_the_days_log_names_menu_dishes_and_quick_adds(client):
    uid = with_goal(client)
    dish = client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": 1.5}).json()  # 300 kcal chicken
    client.post(f"/users/{uid}/food-logs", json={"name": "Latte", "kcal": 190, "date": DAY})

    logs = {l["id"]: l for l in client.get(f"/users/{uid}/food-logs?date={DAY}").json()}
    menu = logs[dish["id"]]
    assert menu["name"] and menu["hall"] and menu["kcal"] == 450 and menu["servings"] == 1.5
    quick = next(l for l in logs.values() if l["item_id"] is None)
    assert quick["name"] == "Latte" and quick["kcal"] == 190 and quick["hall"] is None

    # A misclick comes off the day
    assert client.delete(f"/users/{uid}/food-logs/{dish['id']}").status_code == 204
    assert [l["name"] for l in client.get(f"/users/{uid}/food-logs?date={DAY}").json()] == ["Latte"]
