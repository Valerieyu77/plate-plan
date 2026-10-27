"""
Goal timelines: "lose 10 lb by Dec 20" -> how many calories a day, and whether that pace is safe.
Plain functions, no database access. Weight in lbs, height in inches (same as the User table).

The pace is checked against common public-health guidance (e.g. the CDC's 1-2 lb a week for loss):
  healthy     loss up to 1 lb/week, gain up to 0.5 lb/week
  aggressive  loss up to 2 lb/week (and at most 1% of body weight a week), gain up to 1 lb/week;
              allowed, with a warning
  unsafe      anything faster, a calorie target under the safe minimum, a target weight under a
              BMI of 18.5, or less than a week to get there; not saved. The plan then offers the
              earliest safe date for the same goal, and the most that can safely change by the date.
This is a rough model (about 3,500 kcal per lb of body weight), not medical advice. It is corrected
as the user logs their weight: see replan().
"""

import math
from datetime import date, timedelta

from .nutrition import calorie_floor, daily_targets, missing_profile_fields, tdee

KCAL_PER_LB = 3500

MIN_DAYS = 7
MAX_DAYS = 2 * 365
MAINTAIN_BAND_LBS = 1.0  # a target within 1 lb of the current weight counts as maintaining

HEALTHY_LOSS_PER_WEEK = 1.0
MAX_LOSS_PER_WEEK = 2.0
MAX_LOSS_SHARE_PER_WEEK = 0.01  # of body weight; caps the 2 lb/week for lighter people
HEALTHY_GAIN_PER_WEEK = 0.5
MAX_GAIN_PER_WEEK = 1.0
MIN_TARGET_BMI = 18.5


def bmi(weight_lbs: float, height_in: float) -> float:
    return 703 * weight_lbs / height_in ** 2


def weight_at_bmi(value: float, height_in: float) -> float:
    return value * height_in ** 2 / 703


def direction_of(change_lbs: float) -> str:
    """'lose', 'gain' or 'maintain' (the goal types used by nutrition.py)."""
    if abs(change_lbs) < MAINTAIN_BAND_LBS:
        return "maintain"
    return "lose" if change_lbs < 0 else "gain"


def max_safe_rate(user, direction: str, today: date | None = None) -> float:
    """Fastest allowed pace in lb/week. For loss it is also limited by the calorie minimum."""
    if direction == "gain":
        return MAX_GAIN_PER_WEEK
    if direction == "lose":
        spare_kcal = max(0.0, tdee(user, today) - calorie_floor(user))
        return min(MAX_LOSS_PER_WEEK, MAX_LOSS_SHARE_PER_WEEK * user.weight_lbs, spare_kcal * 7 / KCAL_PER_LB)
    return 0.0


def _healthy_rate(direction: str) -> float:
    return HEALTHY_LOSS_PER_WEEK if direction == "lose" else HEALTHY_GAIN_PER_WEEK


def _days_needed(change_lbs: float, rate: float) -> int | None:
    return max(MIN_DAYS, math.ceil(abs(change_lbs) / rate * 7)) if rate > 0 else None


def plan_goal(user, target_weight_lbs: float, target_date: date, today: date | None = None) -> dict:
    """
    The plan for reaching target_weight_lbs by target_date, starting from the user's current weight:
    daily targets (as daily_targets() returns them), the pace, a tier ("healthy", "aggressive",
    "unsafe"), the reasons it is unsafe (`issues`, empty otherwise) and safe `alternatives`.
    Raises ValueError for an incomplete profile, or a date in the past or more than 2 years away.
    """
    today = today or date.today()
    missing = missing_profile_fields(user)
    if missing:
        raise ValueError(f"profile is missing: {', '.join(missing)}")
    days = (target_date - today).days
    if days <= 0:
        raise ValueError("target_date must be in the future")
    if days > MAX_DAYS:
        raise ValueError("target_date must be within 2 years")

    change = target_weight_lbs - user.weight_lbs
    direction = direction_of(change)
    weekly = 0.0 if direction == "maintain" else abs(change) / days * 7
    max_rate = max_safe_rate(user, direction, today)
    daily_change = 0.0 if direction == "maintain" else (-1 if direction == "lose" else 1) * weekly * KCAL_PER_LB / 7

    issues = []
    if direction != "maintain" and days < MIN_DAYS:
        issues.append(f"Give yourself at least {MIN_DAYS} days; changes over a few days are mostly water, not fat or muscle.")
    elif direction != "maintain" and weekly > max_rate + 1e-9:
        pace_limit = min(MAX_LOSS_PER_WEEK, MAX_LOSS_SHARE_PER_WEEK * user.weight_lbs) if direction == "lose" else MAX_GAIN_PER_WEEK
        if weekly > pace_limit + 1e-9:
            limit = "2 lb or 1% of your body weight" if direction == "lose" else "1 lb"
            issues.append(f"That is {weekly:.1f} lb a week; more than {limit} a week is not considered safe.")
        else:  # the pace is fine, but this person's calorie needs leave too little room
            issues.append(f"This would mean eating under {calorie_floor(user)} kcal a day, the safe minimum.")
    min_weight = weight_at_bmi(MIN_TARGET_BMI, user.height_in)
    if direction == "lose" and target_weight_lbs < min_weight:
        issues.append(f"{target_weight_lbs:g} lb would be underweight for your height (BMI under {MIN_TARGET_BMI}); "
                      f"the lowest healthy weight is about {math.ceil(min_weight)} lb.")

    if issues:
        tier = "unsafe"
    elif weekly > _healthy_rate(direction):
        tier = "aggressive"
    else:
        tier = "healthy"

    targets = daily_targets(user, direction, today, calorie_offset=daily_change)
    alternatives = None
    if direction != "maintain":
        # The same goal (moved to a healthy weight if it was underweight) by a later date, or the most
        # that can safely change by the chosen date
        safe_target = max(target_weight_lbs, math.ceil(min_weight)) if direction == "lose" else target_weight_lbs
        safe_change = safe_target - user.weight_lbs
        fastest = _days_needed(safe_change, max_rate)
        relaxed = _days_needed(safe_change, min(_healthy_rate(direction), max_rate))
        by_date = None
        if days >= MIN_DAYS and max_rate > 0:
            step = min(abs(safe_change), max_rate * days / 7)
            by_date = round(user.weight_lbs + math.copysign(step, change), 1)
        alternatives = {
            "target_weight_lbs": safe_target,
            "earliest_date": today + timedelta(days=fastest) if fastest else None,
            "recommended_date": today + timedelta(days=relaxed) if relaxed else None,
            "target_weight_by_date": by_date,
        }
        if not fastest:
            issues.append("Your daily calories are already close to the safe minimum, so losing weight safely "
                          "would need more activity rather than eating less.")

    return {
        **targets,
        "goal_type": direction,
        "start_weight_lbs": user.weight_lbs,
        "target_weight_lbs": target_weight_lbs,
        "target_date": target_date,
        "days": days,
        "weekly_rate_lbs": round(weekly, 2),
        "daily_calorie_change": round(daily_change),
        "tier": tier,
        "issues": issues,
        "alternatives": alternatives,
    }


def replan(user, goal_type: str, target_weight_lbs: float, target_date: date, today: date | None = None) -> dict:
    """
    New daily targets after a weigh-in: the pace needed to cover what is left by target_date, never
    faster than the safe maximum (so falling behind pushes the finish date out instead of starving
    the user). Once the target is reached or the date has passed, the targets switch to maintaining.
    Returns daily_targets() plus weekly_rate_lbs (the pace now planned, lb/week).
    """
    today = today or date.today()
    remaining = target_weight_lbs - user.weight_lbs
    days_left = (target_date - today).days
    # Within 1 lb of the target, or past it, counts as reached
    reached = direction_of(remaining) != goal_type
    if goal_type == "maintain" or reached or days_left <= 0:
        return {**daily_targets(user, "maintain", today, calorie_offset=0), "weekly_rate_lbs": 0.0}
    rate = min(abs(remaining) / max(days_left, MIN_DAYS) * 7, max_safe_rate(user, goal_type, today))
    offset = (-1 if goal_type == "lose" else 1) * rate * KCAL_PER_LB / 7
    return {**daily_targets(user, goal_type, today, calorie_offset=offset), "weekly_rate_lbs": round(rate, 2)}


def timeline(goal, weights: list, today: date | None = None) -> dict:
    """
    Planned vs actual weight for the progress chart. `goal` has start_date, start_weight_lbs,
    target_date, target_weight_lbs, goal_type and weekly_rate_lbs; `weights` are WeightLog-like rows
    ({date, weight_lbs}) sorted by date.
    status: "reached", "ahead", "on_track" (within 1 lb of the plan) or "behind".
    """
    today = today or date.today()
    total_days = max(1, (goal.target_date - goal.start_date).days)

    def planned_at(day: date) -> float:
        share = min(1.0, max(0.0, (day - goal.start_date).days / total_days))
        return goal.start_weight_lbs + share * (goal.target_weight_lbs - goal.start_weight_lbs)

    planned = []
    day = goal.start_date
    while day < goal.target_date:
        planned.append({"date": day, "weight_lbs": round(planned_at(day), 1)})
        day += timedelta(days=7)
    planned.append({"date": goal.target_date, "weight_lbs": goal.target_weight_lbs})

    actual = [{"date": w.date, "weight_lbs": w.weight_lbs} for w in weights if w.date >= goal.start_date]
    latest = actual[-1] if actual else {"date": goal.start_date, "weight_lbs": goal.start_weight_lbs}
    remaining = goal.target_weight_lbs - latest["weight_lbs"]
    sign = -1 if goal.goal_type == "lose" else 1  # +: the good direction
    expected = planned_at(latest["date"])

    if goal.goal_type == "maintain":
        status = "on_track" if abs(remaining) < MAINTAIN_BAND_LBS else "behind"
    elif direction_of(remaining) != goal.goal_type:
        status = "reached"
    elif sign * (latest["weight_lbs"] - expected) > 1:
        status = "ahead"
    elif sign * (latest["weight_lbs"] - expected) < -1:
        status = "behind"
    else:
        status = "on_track"

    finish = None
    if status != "reached" and goal.goal_type != "maintain" and goal.weekly_rate_lbs:
        finish = max(today, latest["date"]) + timedelta(days=math.ceil(abs(remaining) / goal.weekly_rate_lbs * 7))
    return {
        "goal_type": goal.goal_type,
        "start_date": goal.start_date,
        "start_weight_lbs": goal.start_weight_lbs,
        "target_date": goal.target_date,
        "target_weight_lbs": goal.target_weight_lbs,
        "weekly_rate_lbs": goal.weekly_rate_lbs,
        "planned": planned,
        "actual": actual,
        "latest_weight_lbs": latest["weight_lbs"],
        "expected_weight_lbs": round(expected, 1),
        "remaining_lbs": round(remaining, 1),
        "status": status,
        "projected_finish_date": finish,
    }
