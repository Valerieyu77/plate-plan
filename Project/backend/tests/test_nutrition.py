from datetime import date
from types import SimpleNamespace as NS

import pytest

from app.nutrition import age_from_birthdate, bmr, daily_targets, missing_profile_fields

TODAY = date(2026, 10, 8)


def person(**kw):
    base = dict(weight_lbs=140, height_in=64, gender="female", birthdate=date(2004, 5, 17), activity_level="light")
    return NS(**{**base, **kw})


def test_age_before_and_after_birthday():
    assert age_from_birthdate(date(2004, 10, 9), TODAY) == 21
    assert age_from_birthdate(date(2004, 10, 8), TODAY) == 22


def test_bmr_matches_hand_calculation():
    # 140 lb = 63.50 kg, 64 in = 162.56 cm, age 22, female: 10*63.50 + 6.25*162.56 - 5*22 - 161
    assert bmr(140, 64, 22, "female") == pytest.approx(1380.0, abs=1.5)
    assert bmr(140, 64, 22, "male") == pytest.approx(1380.0 + 166, abs=1.5)


def test_targets_for_each_goal_differ_by_the_offset():
    maintain = daily_targets(person(), "maintain", TODAY)["calorie_goal"]
    assert daily_targets(person(), "lose", TODAY)["calorie_goal"] == pytest.approx(maintain - 450, abs=1)
    assert daily_targets(person(), "gain", TODAY)["calorie_goal"] == pytest.approx(maintain + 400, abs=1)


def test_maintain_calories_are_bmr_times_activity_factor():
    t = daily_targets(person(), "maintain", TODAY)
    assert t["calorie_goal"] == pytest.approx(1380 * 1.375, abs=3)


def test_macros_add_up_to_the_calorie_target():
    t = daily_targets(person(), "lose", TODAY)
    total = 4 * t["protein_goal_g"] + 4 * t["carb_goal_g"] + 9 * t["fat_goal_g"]
    assert total == pytest.approx(t["calorie_goal"], abs=15)
    assert t["protein_goal_g"] == pytest.approx(2.0 * 63.5, abs=1)


def test_activity_level_changes_the_target():
    low = daily_targets(person(activity_level="sedentary"), "maintain", TODAY)["calorie_goal"]
    high = daily_targets(person(activity_level="very_active"), "maintain", TODAY)["calorie_goal"]
    assert high > low


def test_missing_activity_level_uses_the_default():
    assert daily_targets(person(activity_level=None), "maintain", TODAY) == daily_targets(person(), "maintain", TODAY)


def test_safe_minimum_kicks_in_with_a_warning():
    small = person(weight_lbs=95, height_in=58, activity_level="sedentary")
    t = daily_targets(small, "lose", TODAY)
    assert t["calorie_goal"] == 1200
    assert "minimum" in t["warning"]


def test_no_warning_normally():
    assert daily_targets(person(), "maintain", TODAY)["warning"] is None


def test_incomplete_profile_is_rejected():
    assert missing_profile_fields(person(weight_lbs=None, gender="")) == ["weight_lbs", "gender"]
    with pytest.raises(ValueError, match="missing"):
        daily_targets(person(height_in=None), "lose", TODAY)


def test_unknown_goal_type_is_rejected():
    with pytest.raises(ValueError):
        daily_targets(person(), "bulk", TODAY)


# ---------- per-meal split, cross-meal adjustment, progress ----------

from app.nutrition import day_progress, goal_to_targets, item_nutrients, meal_target  # noqa: E402

DAILY = {"kcal": 2000, "protein_g": 100, "carbs_g": 250, "fat_g": 60}
NOTHING_EATEN = {}


def test_first_meal_of_the_day_gets_its_weighted_share():
    r = meal_target(DAILY, NOTHING_EATEN, "breakfast")
    assert r["target"]["kcal"] == pytest.approx(2000 * 0.25)  # 0.25 / (0.25+0.35+0.40)
    assert r["remaining_day"]["kcal"] == 2000


def test_each_meal_gets_the_weighted_share_of_the_day_when_nothing_is_logged():
    assert meal_target(DAILY, {}, "lunch")["target"]["kcal"] == pytest.approx(2000 * 0.35, abs=0.1)
    # dinner with nothing logged is dinner's 40% of the day, not the whole day
    assert meal_target(DAILY, {}, "dinner")["target"]["kcal"] == pytest.approx(2000 * 0.40, abs=0.1)


def test_unlogged_earlier_meals_still_count_as_still_to_come():
    # the user may just not have logged breakfast and lunch yet
    r = meal_target(DAILY, {}, "dinner")
    assert r["target"]["kcal"] < DAILY["kcal"] / 2


def test_a_logged_later_meal_is_not_shared_again():
    eaten = {"dinner": {"kcal": 900, "protein_g": 40, "carbs_g": 100, "fat_g": 30}}
    r = meal_target(DAILY, eaten, "lunch")
    # 1100 kcal left, shared between lunch and the unlogged breakfast: 0.35 / (0.25 + 0.35)
    assert r["target"]["kcal"] == pytest.approx(1100 * 0.35 / 0.60, abs=0.1)


def test_cross_meal_adjustment_after_a_big_breakfast():
    eaten = {"breakfast": {"kcal": 800, "protein_g": 30, "carbs_g": 100, "fat_g": 30}}
    r = meal_target(DAILY, eaten, "lunch")
    assert r["remaining_day"]["kcal"] == 1200
    assert r["target"]["kcal"] == pytest.approx(1200 * 0.35 / 0.75, abs=0.1)
    assert r["target"]["protein_g"] == pytest.approx(70 * 0.35 / 0.75, abs=0.1)


def test_half_logged_meal_asks_for_the_rest_of_that_meal():
    eaten = {"lunch": {"kcal": 300, "protein_g": 10, "carbs_g": 40, "fat_g": 10}}
    r = meal_target(DAILY, eaten, "lunch")
    budget = 2000 * 0.35  # nothing else logged, so lunch gets its 35% of the day
    assert r["meal_budget"]["kcal"] == pytest.approx(budget, abs=0.1)
    assert r["target"]["kcal"] == pytest.approx(budget - 300, abs=0.1)
    assert r["consumed_this_meal"]["kcal"] == 300


def test_light_lunch_and_lunch_share_the_midday_slot():
    eaten = {"light lunch": {"kcal": 200, "protein_g": 5, "carbs_g": 30, "fat_g": 5}}
    r = meal_target(DAILY, eaten, "lunch")
    assert r["consumed_this_meal"]["kcal"] == 200


def test_target_never_goes_negative_when_the_day_is_used_up():
    eaten = {"breakfast": {"kcal": 2500, "protein_g": 200, "carbs_g": 300, "fat_g": 100}}
    r = meal_target(DAILY, eaten, "dinner")
    assert all(v == 0 for v in r["target"].values())
    assert all(v == 0 for v in r["remaining_day"].values())


def test_unknown_meal_is_rejected():
    with pytest.raises(ValueError, match="unknown meal"):
        meal_target(DAILY, {}, "salad bar")


def test_day_progress_reports_remaining_and_over():
    p = day_progress(DAILY, {"kcal": 2300, "protein_g": 60, "carbs_g": 250, "fat_g": 70})
    assert p["remaining"] == {"kcal": 0, "protein_g": 40, "carbs_g": 0, "fat_g": 0}
    assert p["over"]["kcal"] == 300 and p["over"]["fat_g"] == 10 and p["over"]["protein_g"] == 0


def test_item_nutrients_scale_with_servings_and_ignore_missing_values():
    item = NS(kcal=200, protein_g=10, carbs_g=None, fat_g=5)
    assert item_nutrients(item, 1.5) == {"kcal": 300, "protein_g": 15, "carbs_g": 0, "fat_g": 7.5}


def test_goal_to_targets_treats_unset_as_zero():
    g = NS(calorie_goal=1800, protein_goal_g=None, carb_goal_g=200, fat_goal_g=50)
    assert goal_to_targets(g) == {"kcal": 1800, "protein_g": 0, "carbs_g": 200, "fat_g": 50}


# ---------- macros must fit inside the calorie target ----------

def test_macros_are_scaled_to_fit_the_calories_left_keeping_protein():
    # raw leftovers for lunch would be protein ~44 g, carbs ~93 g, fat ~5 g (about 590 kcal) but only ~233 kcal are left
    eaten = {"breakfast": {"kcal": 1500, "protein_g": 5, "carbs_g": 50, "fat_g": 50}}
    t = meal_target(DAILY, eaten, "lunch")["target"]
    implied = 4 * t["protein_g"] + 4 * t["carbs_g"] + 9 * t["fat_g"]
    assert implied <= t["kcal"] + 1
    assert t["kcal"] == pytest.approx(500 * 0.35 / 0.75, abs=0.1)  # calories are not touched
    assert t["protein_g"] == pytest.approx(95 * 0.35 / 0.75, abs=0.1)  # protein is kept first
    assert t["carbs_g"] / t["fat_g"] == pytest.approx(200 / 10, rel=0.1)  # carbs and fat keep their ratio


def test_when_not_even_the_protein_fits_all_calories_go_to_protein():
    eaten = {"breakfast": {"kcal": 1900, "protein_g": 0, "carbs_g": 0, "fat_g": 0}}
    t = meal_target(DAILY, eaten, "dinner")["target"]
    assert t["carbs_g"] == 0 and t["fat_g"] == 0
    assert t["protein_g"] == pytest.approx(t["kcal"] / 4, abs=0.1)


def test_macros_are_left_alone_when_they_already_fit():
    t = meal_target(DAILY, {}, "lunch")["target"]
    assert t["protein_g"] == pytest.approx(100 * 0.35, abs=0.1)
    assert t["carbs_g"] == pytest.approx(250 * 0.35, abs=0.1)


def test_everything_is_zero_when_no_calories_are_left():
    eaten = {"breakfast": {"kcal": 2600, "protein_g": 10, "carbs_g": 10, "fat_g": 10}}
    t = meal_target(DAILY, eaten, "dinner")["target"]
    assert t == {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}


# ---------- meal groups ----------

from app.nutrition import MEAL_GROUP, meals_in_group  # noqa: E402


def test_meals_in_group():
    assert meals_in_group("lunch") == ["light lunch", "lunch", "kosher lunch"]
    assert meals_in_group("Dinner") == ["dinner", "kosher dinner"]
    assert meals_in_group("breakfast") == ["breakfast"]
    assert meals_in_group("Light Lunch") == ["light lunch"]  # a raw name only matches itself


def test_every_meal_has_a_group_and_a_slot():
    from app.nutrition import MEAL_SLOT
    assert set(MEAL_GROUP) == set(MEAL_SLOT)
