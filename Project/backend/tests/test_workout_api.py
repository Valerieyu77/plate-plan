from datetime import date, timedelta

import pytest

from app import events
from tests.test_api import DAY, PASSWORD, PROFILE, client, log_in_as, make_user  # noqa: F401 (client is a fixture)

TODAY = date.today()


def with_goal(client, **goal):
    uid = make_user(client)
    r = client.put(f"/users/{uid}/goal", json=goal or {"goal_type": "lose"})
    assert r.status_code == 200, r.text
    return uid


# ---------- exercises and plans ----------

def test_exercise_list_and_filters(client):
    everything = client.get("/exercises").json()
    assert len(everything) >= 25 and all("dose" not in e for e in everything)
    assert all(e["kind"] == "cardio" for e in client.get("/exercises?kind=cardio").json())
    assert all("back" in e["muscles"] for e in client.get("/exercises?muscle=back").json())
    assert all("dumbbell" in e["equipment"].lower() for e in client.get("/exercises?equipment=dumbbell").json())


def test_workout_plan_follows_the_goal_and_the_users_choices(client):
    uid = with_goal(client, goal_type="gain")
    plan = client.get(f"/users/{uid}/workout?date={DAY}").json()
    assert plan["focus"] == "strength" and plan["intensity"] == "moderate" and plan["total_kcal"] > 0
    assert all({"equipment", "how_to", "video_url", "kcal"} <= set(e) for e in plan["exercises"])
    assert plan == client.get(f"/users/{uid}/workout?date={DAY}").json()  # same day, same plan

    legs = client.get(f"/users/{uid}/workout?muscles=legs,glutes&minutes=30&intensity=light&no_equipment=true").json()
    strength = [e for e in legs["exercises"] if e["kind"] == "strength"]
    assert legs["intensity"] == "light" and strength and all({"legs", "glutes"} & set(e["muscles"]) for e in strength)

    # "Show me another": avoiding what was shown gives different moves
    shown = [e["id"] for e in plan["exercises"] if e["kind"] == "strength"]
    other = client.get(f"/users/{uid}/workout?date={DAY}&avoid={','.join(shown)}").json()
    new = [e["id"] for e in other["exercises"] if e["kind"] == "strength"]
    assert len(set(new) - set(shown)) >= len(new) - 1


def test_workout_plan_without_a_goal_is_mixed(client):
    uid = make_user(client)
    assert client.get(f"/users/{uid}/workout").json()["focus"] == "mixed"


@pytest.mark.parametrize("query", ["intensity=extreme", "minutes=3", "muscles=toes", "focus=yoga"])
def test_bad_workout_choices_are_422(client, query):
    uid = make_user(client)
    assert client.get(f"/users/{uid}/workout?{query}").status_code == 422


def test_workout_endpoints_are_private(client):
    uid = make_user(client)
    other = make_user(client, email="other@example.com")
    assert client.get(f"/users/{uid}/workout").status_code == 403
    assert client.get(f"/users/{uid}/workout-logs").status_code == 403
    assert client.get(f"/users/{uid}/energy?date={DAY}").status_code == 403
    client.headers.pop("Authorization")
    assert client.get(f"/users/{other}/goal/progress").status_code == 401


# ---------- workout logs ----------

def test_log_an_exercise_from_the_list_or_your_own(client):
    uid = make_user(client)  # 140 lb
    r = client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "treadmill", "minutes": 30, "date": DAY})
    assert r.status_code == 201, r.text
    # 6 METs (moderate treadmill) x 63.5 kg x 0.5 h
    assert r.json()["kcal"] == pytest.approx(6.0 * 140 / 2.20462 * 0.5, abs=0.1) and r.json()["name"] == "Treadmill walk or run"

    own = client.post(f"/users/{uid}/workout-logs", json={"name": "Badminton", "minutes": 45, "kcal": 250, "date": DAY})
    assert own.status_code == 201 and own.json()["exercise_id"] is None
    watch = client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "bike", "minutes": 20, "kcal": 180})
    assert watch.json()["kcal"] == 180  # the user's own number wins

    assert client.post(f"/users/{uid}/workout-logs", json={"name": "Badminton", "minutes": 45}).status_code == 422
    assert client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "flying", "minutes": 10}).status_code == 422
    assert client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "bike", "minutes": 0}).status_code == 422

    assert len(client.get(f"/users/{uid}/workout-logs?date={DAY}").json()) == 2
    assert client.delete(f"/users/{uid}/workout-logs/{own.json()['id']}").status_code == 204
    assert client.delete(f"/users/{uid}/workout-logs/{own.json()['id']}").status_code == 404
    assert len(client.get(f"/users/{uid}/workout-logs").json()) == 2


# ---------- energy and progress ----------

def test_energy_for_a_day_counts_food_and_workouts(client):
    # PROFILE is "moderate" (4-5 workouts a week): an average day's exercise is already in the burn
    uid = with_goal(client)
    calorie_goal = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": 2})  # 600 kcal of chicken on DAY
    client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "treadmill", "minutes": 30, "date": DAY})
    e = client.get(f"/users/{uid}/energy?date={DAY}").json()
    walk = 6.0 * 140 / 2.20462 * 0.5  # about 190.5 kcal
    assert e["exercise_logged"] == pytest.approx(walk, abs=1)
    assert e["exercise_in_activity"] > walk and e["exercise"] == 0  # a normal workout day: nothing counts twice
    assert e["eaten"] == 600 and e["burned"] == e["base_burn"] and e["net"] == 600 - e["burned"]
    assert e["calorie_goal"] == calorie_goal
    assert e["vs_plan"] == pytest.approx(-(600 - calorie_goal), abs=1) and e["status"] == "too_low"  # 600 kcal is under the safe minimum
    assert len(e["workouts"]) == 1 and e["burn_adjusted"] is False

    # A much longer session than usual adds only what goes beyond the usual
    client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "treadmill", "minutes": 120, "intensity": "hard", "date": DAY})
    big = client.get(f"/users/{uid}/energy?date={DAY}").json()
    assert big["exercise"] == pytest.approx(big["exercise_logged"] - big["exercise_in_activity"], abs=1) and big["exercise"] > 0
    assert big["burned"] == pytest.approx(big["base_burn"] + big["exercise"], abs=1)

    empty = client.get(f"/users/{uid}/energy?date=2026-10-09").json()
    assert empty["status"] == "not_logged" and empty["eaten"] is None


def test_someone_who_said_not_active_gets_every_workout_counted(client):
    uid = make_user(client, activity_level="sedentary")
    client.put(f"/users/{uid}/goal", json={"goal_type": "lose"})
    client.post(f"/users/{uid}/workout-logs", json={"exercise_id": "treadmill", "minutes": 30, "date": DAY})
    e = client.get(f"/users/{uid}/energy?date={DAY}").json()
    assert e["exercise_in_activity"] == 0 and e["exercise"] == e["exercise_logged"] > 0


def test_energy_needs_a_goal(client):
    uid = make_user(client)
    assert client.get(f"/users/{uid}/energy?date={DAY}").status_code == 404


def test_goal_progress_for_a_timeline_goal(client):
    uid = with_goal(client, target_weight_lbs=132, target_date=str(TODAY + timedelta(days=84)))
    yesterday = TODAY - timedelta(days=1)
    goal = client.get(f"/users/{uid}/goal").json()
    assert goal["start_date"] == str(TODAY)

    p = client.get(f"/users/{uid}/goal/progress?date={TODAY + timedelta(days=3)}").json()
    assert p["days_logged"] == 0 and p["status"] == "not_logged"
    assert p["weight"]["from_weight_lbs"] == 140 and p["scale"]["status"] == "on_track"
    assert p["calibration"]["factor"] == 1.0

    # Two days 300 kcal under the plan (still a safe pace): ahead, so it should finish early
    light = round((goal["calorie_goal"] - 300) / 300, 2)  # item 1 is 300 kcal a serving
    for d in (TODAY, TODAY + timedelta(days=1)):
        client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": light, "date": str(d)})
    p = client.get(f"/users/{uid}/goal/progress?date={TODAY + timedelta(days=3)}").json()
    assert p["days_logged"] == 2 and p["status"] == "ahead" and p["days_earlier"] > 0
    assert p["projected_finish_date"] < goal["target_date"]
    assert p["weight"]["estimated_weight_lbs"] < 140 and "ahead of plan" in p["message"]
    assert p["ahead_kcal"] == pytest.approx(2 * 300, abs=2)
    assert yesterday < TODAY  # (yesterday isn't logged and doesn't count)


def test_a_weigh_in_restarts_the_count_so_following_the_plan_is_never_behind(client):
    uid = with_goal(client, target_weight_lbs=132, target_date=str(TODAY + timedelta(days=84)))
    plan = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    for i in range(14):  # exactly the plan
        client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": round(plan / 300, 2),
                                                     "date": str(TODAY + timedelta(days=i))})
    # Heavier on the scale: the weigh-in replans to fewer calories, which must not rescore the 14 days
    client.post(f"/users/{uid}/weight-logs", json={"weight_lbs": 143, "date": str(TODAY + timedelta(days=14))})
    assert client.get(f"/users/{uid}/goal").json()["calorie_goal"] < plan
    p = client.get(f"/users/{uid}/goal/progress?date={TODAY + timedelta(days=14)}").json()
    assert p["since"] == str(TODAY + timedelta(days=14)) and p["since_weigh_in"] is True
    assert p["days_logged"] == 0 and p["status"] == "not_logged" and "weigh-in updated your plan" in p["message"]
    assert p["scale"]["status"] == "behind"  # the scale still says so


def test_eating_under_the_minimum_is_flagged_not_praised(client):
    uid = with_goal(client, target_weight_lbs=132, target_date=str(TODAY + timedelta(days=84)))
    for i in range(7):  # 600 kcal a day
        client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": 2, "date": str(TODAY + timedelta(days=i))})
    p = client.get(f"/users/{uid}/goal/progress?date={TODAY + timedelta(days=7)}").json()
    assert p["status"] == "unsafe_pace" and p["days_earlier"] is None and p["projected_finish_date"] is None
    assert "safe minimum" in p["message"] and "early" not in p["message"]


def test_goal_progress_without_a_timeline_looks_at_the_last_four_weeks(client):
    uid = with_goal(client, goal_type="maintain")
    p = client.get(f"/users/{uid}/goal/progress").json()
    assert p["days"] == 28 and p["days_earlier"] is None and p["scale"] is None


# ---------- campus events ----------

def test_events_endpoint(client, monkeypatch):
    from tests.test_events import ICS

    monkeypatch.setattr(events, "fetch_events", lambda: events.parse_ics(ICS))
    r = client.get("/events?start=2026-10-28&days=7").json()
    assert [e["title"] for e in r["events"]] == ["Lunch Skate", "Sunrise Yoga on the Quad"]
    assert r["source"].startswith("https://calendars.illinois.edu/")
    assert len(client.get("/events?start=2026-10-28&days=7&fitness_only=false").json()["events"]) == 3
    assert client.get("/events?days=90").status_code == 422


def test_events_endpoint_when_the_calendar_is_down(client, monkeypatch):
    import requests

    def down():
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(events, "fetch_events", down)
    assert client.get("/events").status_code == 503


def test_today_is_in_progress_not_ahead(client):
    from app.main import _today

    uid = with_goal(client)
    today = str(_today())
    client.post(f"/users/{uid}/food-logs", json={"item_id": 1, "servings": 1, "date": today})  # just one meal so far
    e = client.get(f"/users/{uid}/energy?date={today}").json()
    assert e["status"] == "in_progress" and e["day_complete"] is False and e["eaten"] == 300
    past = client.get(f"/users/{uid}/energy?date=2026-10-08").json()
    assert past["day_complete"] is True and past["status"] == "not_logged"
    p = client.get(f"/users/{uid}/goal/progress").json()
    assert "once the day is over" in p["message"]


def test_campus_today_is_chicago_time(monkeypatch):
    from datetime import datetime, timezone

    import app.main as main

    class Late(datetime):  # 1:30 am UTC on Nov 9 is still the evening of Nov 8 in Illinois
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 9, 1, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(main, "datetime", Late)
    assert main._today() == date(2026, 11, 8)


def test_a_plate_never_gets_more_than_two_servings_of_a_dish(client):
    uid = with_goal(client, goal_type="gain")
    for meal in ("lunch", "dinner"):
        rec = client.get(f"/recommendations/meals?user_id={uid}&hall=Illinois Street Dining Center (ISR)&date={DAY}&meal={meal}").json()
        assert all(l["servings"] <= 2 for l in rec["items"]), rec


def test_servings_cap_is_two_even_for_a_big_meal():
    from app.main import _servings_cap

    assert _servings_cap({"kcal": 600}) == 2 and _servings_cap({"kcal": 1200}) == 2  # more dishes, not bigger heaps
