"""Choosing which meals you eat each day: the day's calories are shared between those meals only."""

from datetime import date, timedelta

import pytest

from app.nutrition import meal_target
from tests.test_api import DAY, client, make_user  # noqa: F401 (client is a fixture)

DAILY = {"kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 65}


def kcal(meal, meals_eaten=None, eaten=None):
    return meal_target(DAILY, eaten or {}, meal, meals_eaten)["target"]["kcal"]


def test_three_meals_is_the_default():
    assert kcal("dinner") == kcal("dinner", ["breakfast", "lunch", "dinner"]) == pytest.approx(800, abs=0.5)


def test_skipping_lunch_shares_the_day_between_breakfast_and_dinner():
    meals = ["breakfast", "dinner"]
    assert kcal("breakfast", meals) == pytest.approx(2000 * 0.25 / 0.65, abs=0.5)  # about 769
    assert kcal("dinner", meals) == pytest.approx(2000 * 0.40 / 0.65, abs=0.5)  # about 1231
    assert kcal("breakfast", meals) + kcal("dinner", meals) == pytest.approx(2000, abs=1)


def test_one_meal_a_day_gets_the_whole_day():
    assert kcal("dinner", ["dinner"]) == pytest.approx(2000, abs=0.5)


def test_a_meal_outside_the_routine_still_gets_a_share_and_counts_once_eaten():
    meals = ["breakfast", "dinner"]
    # Asking about lunch anyway: it counts alongside the planned meals
    assert kcal("lunch", meals) == pytest.approx(2000 * 0.35 / 1.0, abs=0.5)
    # A lunch that was eaten is taken off the day before dinner is worked out
    lunch = {"lunch": {"kcal": 600, "protein_g": 40, "carbs_g": 60, "fat_g": 20}}
    assert kcal("dinner", meals, lunch) == pytest.approx((2000 - 600) * 0.40 / 0.65, abs=0.5)


def test_the_meals_endpoint_validates_and_changes_the_meal_target(client):
    uid = make_user(client)
    client.put(f"/users/{uid}/goal", json={"goal_type": "maintain"})
    daily = client.get(f"/users/{uid}/goal").json()["calorie_goal"]
    three = client.get(f"/users/{uid}/meal-target?date={DAY}&meal=dinner").json()
    assert three["meals_eaten"] == ["breakfast", "lunch", "dinner"]

    r = client.put(f"/users/{uid}/meals", json={"meals": ["Dinner", "breakfast", "dinner"]})
    assert r.status_code == 200 and r.json()["meals"] == ["breakfast", "dinner"]  # cleaned up, in day order
    assert client.get(f"/users/{uid}").json()["meals"] == ["breakfast", "dinner"]

    two = client.get(f"/users/{uid}/meal-target?date={DAY}&meal=dinner").json()
    assert two["meals_eaten"] == ["breakfast", "dinner"]
    assert two["meal_budget"]["kcal"] == pytest.approx(daily * 0.40 / 0.65, abs=1)
    assert two["meal_budget"]["kcal"] > three["meal_budget"]["kcal"]

    # The bigger budget reaches the recommendation and the hall picks
    rec = client.get(f"/recommendations/meals?user_id={uid}&hall=Illinois Street Dining Center (ISR)&date={DAY}&meal=dinner")
    assert rec.json()["target"]["kcal"] == pytest.approx(two["target"]["kcal"], abs=1)

    assert client.put(f"/users/{uid}/meals", json={"meals": ["brunch"]}).status_code == 422
    assert client.put(f"/users/{uid}/meals", json={"meals": []}).status_code == 422
    back = client.put(f"/users/{uid}/meals", json={"meals": None})
    assert back.status_code == 200 and back.json()["meals"] is None


def test_meals_can_be_chosen_at_sign_up(client):
    uid = make_user(client, meals=["lunch", "dinner"])
    assert client.get(f"/users/{uid}").json()["meals"] == ["lunch", "dinner"]


def test_only_the_owner_can_change_meals(client):
    uid = make_user(client)
    make_user(client, email="other@example.com")
    assert client.put(f"/users/{uid}/meals", json={"meals": ["dinner"]}).status_code == 403
