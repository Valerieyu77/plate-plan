from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.energy import (
    FACTOR_LIMITS, KCAL_PER_LB, calibrate, day_balance, estimate_weight, goal_progress, progress_message,
    smoothed_weight,
)

TODAY = date(2026, 11, 1)
BURN = 2000


def w(day, lbs):
    return SimpleNamespace(date=day, weight_lbs=lbs)


def goal(**kw):
    base = dict(goal_type="lose", calorie_goal=1500, start_date=TODAY - timedelta(days=10), target_date=None,
                weekly_rate_lbs=None, start_weight_lbs=160)
    return SimpleNamespace(**{**base, **kw})


def logged(n, eaten, exercise=0, end=TODAY):
    """n days of the same intake, ending the day before `end`."""
    return {end - timedelta(days=i): {"eaten": eaten, "exercise": exercise} for i in range(1, n + 1)}


# ---------- one day ----------

def test_a_day_on_plan():
    d = day_balance("lose", 1500, BURN, 1500, 0)
    assert d["net"] == -500 and d["planned_net"] == -500 and d["vs_plan"] == 0 and d["status"] == "on_track"


def test_a_workout_puts_a_losing_day_ahead_and_overeating_puts_it_behind():
    assert day_balance("lose", 1500, BURN, 1500, 300) == pytest.approx(
        {"eaten": 1500, "base_burn": 2000, "exercise": 300, "burned": 2300, "net": -800, "planned_net": -500,
         "vs_plan": 300, "status": "ahead"})
    assert day_balance("lose", 1500, BURN, 1900, 0)["status"] == "behind"


def test_gaining_counts_a_surplus_as_progress():
    assert day_balance("gain", 2400, BURN, 2700, 0)["status"] == "ahead"
    assert day_balance("gain", 2400, BURN, 2400, 400)["status"] == "behind"  # burned what was meant to be stored


def test_maintain_says_over_or_under():
    assert day_balance("maintain", 2000, BURN, 2100, 0)["status"] == "on_track"
    assert day_balance("maintain", 2000, BURN, 2500, 0)["status"] == "over"
    assert day_balance("maintain", 2000, BURN, 1500, 0)["status"] == "under"


def test_ahead_or_behind_does_not_depend_on_the_burn_estimate():
    for burn in (1700, 2000, 2400):
        assert day_balance("lose", 1500, burn, 1400, 200)["vs_plan"] == 300


def test_a_day_without_food_logs_is_unknown_not_zero():
    d = day_balance("lose", 1500, BURN, None, 200)
    assert d["eaten"] is None and d["net"] is None and d["status"] == "not_logged" and d["exercise"] == 200


# ---------- adding the days up ----------

def test_progress_adds_up_logged_days_only_and_skips_today():
    days = {**logged(4, 1300), TODAY: {"eaten": 0, "exercise": 0}}
    days[TODAY - timedelta(days=6)] = {"eaten": None, "exercise": 500}  # a workout but no food logged
    p = goal_progress(goal(), days, BURN, TODAY)
    assert p["days_logged"] == 4 and p["days"] == 10
    assert p["ahead_kcal"] == 800 and p["ahead_lbs"] == pytest.approx(800 / KCAL_PER_LB, abs=0.01)
    assert p["status"] == "ahead" and p["days_earlier"] is None  # no timeline: no finish date


def test_a_timeline_goal_finishes_earlier_when_ahead_and_later_when_behind():
    # 1 lb a week is 500 kcal a day; 1,500 kcal ahead is 3 days early
    g = goal(target_date=TODAY + timedelta(days=60), weekly_rate_lbs=1.0)
    ahead = goal_progress(g, logged(3, 1000), BURN, TODAY)
    assert ahead["days_earlier"] == 3 and ahead["projected_finish_date"] == g.target_date - timedelta(days=3)
    behind = goal_progress(g, logged(5, 1800), BURN, TODAY)
    assert behind["status"] == "behind" and behind["days_earlier"] == -3
    assert behind["projected_finish_date"] == g.target_date + timedelta(days=3)
    assert "3 days late" in progress_message(behind, "lose")


def test_progress_with_nothing_logged():
    p = goal_progress(goal(), {}, BURN, TODAY)
    assert p["status"] == "not_logged" and p["ahead_kcal"] == 0
    assert "Log what you eat" in progress_message(p, "lose")


# ---------- weigh-ins and the scale ----------

def test_smoothing_averages_the_last_week():
    weights = [w(TODAY - timedelta(days=9), 170), w(TODAY - timedelta(days=4), 161), w(TODAY, 159)]
    assert smoothed_weight(weights, TODAY) == 160


def test_estimated_weight_starts_from_the_latest_weigh_in_and_adds_the_logs_since():
    weights = [w(TODAY - timedelta(days=5), 160)]
    days = logged(4, 1500)  # 4 days of a 500 kcal deficit after the weigh-in
    est = estimate_weight(weights, days, BURN, 165, TODAY - timedelta(days=30), TODAY)
    assert est["from_weight_lbs"] == 160 and est["estimated_weight_lbs"] == pytest.approx(160 - 2000 / KCAL_PER_LB, abs=0.05)


def test_estimated_weight_without_weigh_ins_uses_the_start_weight():
    est = estimate_weight([], logged(7, 1500), BURN, 165, TODAY - timedelta(days=8), TODAY)
    assert est["from_weight_lbs"] == 165 and est["estimated_weight_lbs"] == pytest.approx(164, abs=0.05)


def calibration_case(real_burn, logged_days=28, span=28, eaten=1800):
    """Weigh-ins `span` days apart that match someone who really burns `real_burn` a day."""
    start = TODAY - timedelta(days=span)
    change = (eaten - real_burn) * span / KCAL_PER_LB
    weights = [w(start, 160), w(start + timedelta(days=2), 160), w(TODAY - timedelta(days=1), 160 + change), w(TODAY, 160 + change)]
    days = {start + timedelta(days=i): {"eaten": eaten if i < logged_days else None, "exercise": 0} for i in range(span)}
    return calibrate(days, weights, BURN, TODAY)


def test_calibration_learns_a_lower_burn_from_the_scale():
    c = calibration_case(real_burn=1800)
    assert c["factor"] == pytest.approx(0.9, abs=0.02) and c["burn_estimate"] == pytest.approx(1800, abs=40)
    assert "less than the formula" in c["message"]


def test_calibration_matching_the_formula_changes_nothing():
    c = calibration_case(real_burn=BURN)
    assert c["factor"] == pytest.approx(1.0, abs=0.01) and "match" in c["message"]


def test_calibration_is_capped_and_needs_enough_data():
    assert calibration_case(real_burn=3000)["factor"] <= FACTOR_LIMITS[1]
    assert calibration_case(real_burn=1800, span=10)["factor"] == 1.0  # weigh-ins too close together
    assert calibration_case(real_burn=1800, logged_days=10)["factor"] == 1.0  # too few days logged
    assert calibrate({}, [w(TODAY, 160)], BURN, TODAY)["factor"] == 1.0  # one weigh-in


def test_calibration_trusts_three_weeks_less_than_four():
    three, four = calibration_case(1800, span=21, logged_days=21), calibration_case(1800)
    assert 0.9 < three["factor"] < 1.0 and four["factor"] < three["factor"]


def test_the_food_on_the_day_of_a_weigh_in_counts_after_it():
    start = TODAY - timedelta(days=2)
    days = {start: {"eaten": 1500, "exercise": 0}}
    est = estimate_weight([], days, BURN, 165, start, TODAY)
    assert est["estimated_weight_lbs"] == pytest.approx(165 - 500 / KCAL_PER_LB, abs=0.05)
    assert "1 logged day," in progress_message({"days_logged": 1, "status": "ahead", "ahead_kcal": 500,
                                                "ahead_lbs": 0.14, "days_earlier": 1}, "lose")
