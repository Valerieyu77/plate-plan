from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest

from app.nutrition import tdee
from app.timeline import max_safe_rate, plan_goal, replan, timeline

TODAY = date(2026, 10, 8)


def person(**kw):
    # 140 lb, 5'4": a BMI of 18.5 is about 108 lb; 1% of body weight is 1.4 lb/week
    base = dict(weight_lbs=140, height_in=64, gender="female", birthdate=date(2004, 5, 17), activity_level="moderate")
    return NS(**{**base, **kw})


def weeks(n):
    return TODAY + timedelta(weeks=n)


def test_ten_pounds_in_eight_weeks():
    p = plan_goal(person(weight_lbs=180, height_in=70), 170, weeks(8), TODAY)
    assert p["goal_type"] == "lose"
    assert p["weekly_rate_lbs"] == 1.25
    assert p["daily_calorie_change"] == -625  # 35,000 kcal over 56 days
    assert p["calorie_goal"] == round(tdee(person(weight_lbs=180, height_in=70), TODAY) - 625)
    assert p["tier"] == "aggressive" and p["issues"] == []


def test_a_slow_loss_is_healthy():
    p = plan_goal(person(), 135, weeks(8), TODAY)
    assert p["tier"] == "healthy" and p["weekly_rate_lbs"] == 0.62


def test_twenty_pounds_in_two_days_is_refused_with_a_safe_date():
    p = plan_goal(person(), 120, TODAY + timedelta(days=2), TODAY)
    assert p["tier"] == "unsafe"
    assert "at least 7 days" in p["issues"][0]
    alt = p["alternatives"]
    # Fastest safe pace for this person is 1% of 140 lb = 1.4 lb/week: 20 lb takes 100 days
    assert alt["earliest_date"] == TODAY + timedelta(days=100)
    assert alt["recommended_date"] == TODAY + timedelta(days=140)  # at 1 lb/week
    assert alt["target_weight_by_date"] is None  # 2 days is too short to plan anything


def test_too_fast_offers_what_is_safe_by_that_date():
    p = plan_goal(person(), 110, weeks(4), TODAY)
    assert p["tier"] == "unsafe" and "lb a week" in p["issues"][0]
    assert p["alternatives"]["target_weight_by_date"] == 134.4  # 4 weeks x 1.4 lb


def test_rate_limit_is_lower_for_lighter_people_and_near_the_calorie_minimum():
    assert max_safe_rate(person(weight_lbs=300, height_in=72), "lose", TODAY) == 2.0
    assert max_safe_rate(person(), "lose", TODAY) == pytest.approx(1.4)
    small = person(weight_lbs=110, height_in=60, activity_level="sedentary")
    spare = tdee(small, TODAY) - 1200
    assert max_safe_rate(small, "lose", TODAY) == pytest.approx(spare * 7 / 3500)


def test_a_plan_under_the_calorie_minimum_is_unsafe():
    small = person(weight_lbs=125, height_in=60, activity_level="sedentary")
    p = plan_goal(small, 120, weeks(4), TODAY)  # 1.25 lb/week is under 1% but needs too few calories
    assert p["tier"] == "unsafe" and "1200 kcal" in p["issues"][0]


def test_an_underweight_target_is_unsafe_even_slowly():
    p = plan_goal(person(), 100, weeks(52), TODAY)
    assert p["tier"] == "unsafe" and any("underweight" in i for i in p["issues"])
    assert p["alternatives"]["target_weight_lbs"] == 108


def test_gaining():
    assert plan_goal(person(), 143, weeks(8), TODAY)["tier"] == "healthy"
    assert plan_goal(person(), 145, weeks(8), TODAY)["tier"] == "aggressive"  # 0.62 lb/week
    fast = plan_goal(person(), 150, weeks(4), TODAY)
    assert fast["tier"] == "unsafe" and fast["daily_calorie_change"] > 0
    assert fast["alternatives"]["earliest_date"] == weeks(10)


def test_a_target_within_a_pound_is_maintaining():
    p = plan_goal(person(), 140.5, weeks(4), TODAY)
    assert p["goal_type"] == "maintain" and p["tier"] == "healthy" and p["alternatives"] is None
    assert p["calorie_goal"] == round(tdee(person(), TODAY))


def test_bad_dates_and_profiles_are_rejected():
    with pytest.raises(ValueError, match="future"):
        plan_goal(person(), 130, TODAY, TODAY)
    with pytest.raises(ValueError, match="2 years"):
        plan_goal(person(), 130, TODAY + timedelta(days=800), TODAY)
    with pytest.raises(ValueError, match="weight_lbs"):
        plan_goal(person(weight_lbs=None), 130, weeks(8), TODAY)


def test_replan_spreads_what_is_left_over_the_time_left():
    # Started at 140 aiming for 132 in 8 weeks; 4 weeks in, at 137: 5 lb in 4 weeks
    r = replan(person(weight_lbs=137), "lose", 132, weeks(4), TODAY)
    assert r["weekly_rate_lbs"] == 1.25


def test_replan_never_goes_faster_than_safe():
    r = replan(person(weight_lbs=139), "lose", 130, weeks(2), TODAY)  # would need 4.5 lb/week
    assert r["weekly_rate_lbs"] == pytest.approx(1.39)


def test_replan_switches_to_maintaining_when_done():
    maintain = round(tdee(person(weight_lbs=131.5), TODAY))
    assert replan(person(weight_lbs=131.5), "lose", 132, weeks(2), TODAY)["calorie_goal"] == maintain
    assert replan(person(weight_lbs=129), "lose", 132, weeks(2), TODAY)["weekly_rate_lbs"] == 0
    assert replan(person(weight_lbs=135), "lose", 132, TODAY, TODAY)["weekly_rate_lbs"] == 0  # date passed


def goal(**kw):
    base = dict(goal_type="lose", start_date=TODAY, start_weight_lbs=140, target_date=weeks(8),
                target_weight_lbs=132, weekly_rate_lbs=1.0)
    return NS(**{**base, **kw})


def w(day, lbs):
    return NS(date=day, weight_lbs=lbs)


def test_timeline_has_weekly_planned_points_ending_at_the_target():
    t = timeline(goal(), [], TODAY)
    assert [p["date"] for p in t["planned"]] == [weeks(i) for i in range(9)]
    assert [p["weight_lbs"] for p in t["planned"]][:3] == [140, 139, 138]
    assert t["planned"][-1]["weight_lbs"] == 132
    assert t["status"] == "on_track" and t["latest_weight_lbs"] == 140


def test_timeline_status():
    assert timeline(goal(), [w(weeks(2), 138.2)], weeks(2))["status"] == "on_track"  # plan says 138
    assert timeline(goal(), [w(weeks(2), 136)], weeks(2))["status"] == "ahead"
    behind = timeline(goal(), [w(weeks(2), 140)], weeks(2))
    assert behind["status"] == "behind" and behind["projected_finish_date"] == weeks(10)  # 8 lb at 1 lb/week
    assert timeline(goal(), [w(weeks(6), 131.8)], weeks(6))["status"] == "reached"
    gain = goal(goal_type="gain", target_weight_lbs=146, weekly_rate_lbs=0.75)
    assert timeline(gain, [w(weeks(4), 144.5)], weeks(4))["status"] == "ahead"  # plan says 143


def test_timeline_ignores_weigh_ins_from_before_the_goal():
    t = timeline(goal(), [w(TODAY - timedelta(days=3), 141), w(weeks(1), 139)], weeks(1))
    assert [a["weight_lbs"] for a in t["actual"]] == [139]
