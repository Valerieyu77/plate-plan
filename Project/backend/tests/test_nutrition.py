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
