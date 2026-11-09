"""
Calories in vs calories out, and how that adds up toward the goal. Plain functions, no database.

Two things tell us how the user is doing, and they used to disagree:
  - the food and workout logs: eaten - (daily burn + workouts), every day, but the daily burn is
    only a formula (tdee() in nutrition.py), so it can be off by a few hundred kcal for one person
  - the scale: the real answer, but noisy (water and salt move it 2-4 lb from day to day) and only
    as often as the user weighs in
So the logs give the day-to-day picture and the scale corrects it:
  1. Between weigh-ins, the weight is estimated from the latest (smoothed) weigh-in plus the
     calories logged since.
  2. Weigh-ins are smoothed (the average of the readings within a week of the latest one), so one
     salty dinner doesn't move anything.
  3. Once there are at least two weeks between smoothed weigh-ins with most days logged, the
     weight actually lost or gained shows how much this person really burns. The ratio to the
     formula (`factor`, kept between 0.8 and 1.2, and pulled toward 1 when there is little data)
     is then used for the daily burn. The more the user logs, the closer it gets.

Whether the user is ahead of or behind the plan doesn't depend on the burn estimate at all: the
plan already allows for it, so a day's difference from the plan is just
eaten - workouts - calorie goal (the daily burn cancels out). For a timeline goal, each weigh-in
replans the calorie goal (timeline.replan()), which already makes up for everything before it, so
only the days since the latest weigh-in are added up.

Going faster than planned is only "ahead" while it stays safe: eating under the calorie minimum, or
a real pace beyond the safe maximum (timeline.max_safe_rate()), is flagged instead of praised.

About 3,500 kcal per lb; workouts are estimates too. The activity level picked at sign-up already
counts an average day's exercise, so a logged workout only adds what goes beyond it (count_workouts).
Rough guidance, not medical advice.
"""

import math
from datetime import date, timedelta
from statistics import mean

from .timeline import KCAL_PER_LB

ON_PLAN_KCAL = 100        # within this many kcal a day of the plan counts as on track
SMOOTH_DAYS = 7           # weigh-ins within a week of each other are averaged
MIN_CALIBRATION_DAYS = 14  # between the two smoothed weigh-ins
CALIBRATION_WINDOW = 42   # look back at most this many days
MIN_LOGGED_SHARE = 0.7    # of days between the weigh-ins with food logged
FACTOR_LIMITS = (0.8, 1.2)


def count_workouts(days: dict, in_activity: float) -> dict:
    """
    Stop counting workouts twice. The daily burn (tdee) already includes an average day's exercise
    for the activity level picked at sign-up (`in_activity` kcal), so a logged workout only adds what
    goes beyond that. Each day keeps the logged total as exercise_logged; exercise becomes the extra
    that counts. Someone who picked "not active" has in_activity 0, so all their workouts count.
    """
    for d in days.values():
        logged = d["exercise"]
        d["exercise_logged"] = logged
        d["exercise"] = max(0.0, logged - in_activity)
    return days


def direction_sign(goal_type: str) -> int:
    """-1 when losing (a deficit is progress), +1 when gaining, 0 when maintaining."""
    return {"lose": -1, "gain": 1}.get(goal_type, 0)


def _status(ahead_kcal_per_day: float, goal_type: str) -> str:
    if goal_type == "maintain":
        if abs(ahead_kcal_per_day) <= ON_PLAN_KCAL * 2:
            return "on_track"
        return "over" if ahead_kcal_per_day > 0 else "under"
    if ahead_kcal_per_day > ON_PLAN_KCAL:
        return "ahead"
    if ahead_kcal_per_day < -ON_PLAN_KCAL:
        return "behind"
    return "on_track"


def day_balance(goal_type: str, calorie_goal: float, base_burn: float, eaten: float | None, exercise: float,
                calorie_floor: float | None = None) -> dict:
    """
    One day's ledger. `eaten` is None when nothing was logged (unknown, not zero).
    net < 0 is a deficit. vs_plan is how far the day was from the plan in the goal's direction:
    > 0 is ahead (a bigger deficit when losing, a bigger surplus when gaining). For "maintain",
    vs_plan is simply eaten - workouts - goal, and status says "over" or "under".
    With calorie_floor (pass it only for a day that is over), eating under it is "too_low".
    """
    burned = base_burn + exercise
    planned_net = calorie_goal - base_burn
    if eaten is None:
        return {"eaten": None, "base_burn": round(base_burn), "exercise": round(exercise), "burned": round(burned),
                "net": None, "planned_net": round(planned_net), "vs_plan": None, "status": "not_logged"}
    diff = eaten - exercise - calorie_goal  # = net - planned_net
    sign = direction_sign(goal_type)
    vs_plan = sign * diff if sign else diff
    return {
        "eaten": round(eaten), "base_burn": round(base_burn), "exercise": round(exercise), "burned": round(burned),
        "net": round(eaten - burned), "planned_net": round(planned_net), "vs_plan": round(vs_plan),
        "status": "too_low" if calorie_floor and eaten < calorie_floor else _status(vs_plan, goal_type),
    }


def smoothed_weight(weights: list, around: date) -> float | None:
    """Average of the weigh-ins within SMOOTH_DAYS before `around` (inclusive)."""
    near = [w.weight_lbs for w in weights if around - timedelta(days=SMOOTH_DAYS - 1) <= w.date <= around]
    return round(mean(near), 1) if near else None


def calibrate(days: dict, weights: list, formula_burn: float, today: date) -> dict:
    """
    How the user's real daily burn compares with the formula, from weigh-ins and food logs.
    days: {date: {"eaten": kcal or None, "exercise": kcal}}; weights: WeightLog-like rows sorted by date.
    Returns {"factor", "burn_estimate", "days_used", "message"}; factor 1.0 until there is enough data.
    """
    not_yet = {"factor": 1.0, "burn_estimate": round(formula_burn), "days_used": 0}
    window = [w for w in weights if (today - w.date).days <= CALIBRATION_WINDOW]
    if len(window) < 2:
        return {**not_yet, "message": "Weigh in at least once a week: after two weeks of weigh-ins and food logs, "
                                      "the estimates adjust to how your body really responds."}
    end_day = window[-1].date
    start_day = window[0].date
    span = (end_day - start_day).days
    if span < MIN_CALIBRATION_DAYS:
        return {**not_yet, "message": f"{MIN_CALIBRATION_DAYS - span} more days of weigh-ins until the estimates can adjust to you."}

    # Smooth both ends: the first week of readings, and the last week
    first = [w.weight_lbs for w in window if (w.date - start_day).days < SMOOTH_DAYS]
    last = [w.weight_lbs for w in window if (end_day - w.date).days < SMOOTH_DAYS]
    change = mean(last) - mean(first)

    between = [days.get(start_day + timedelta(days=i)) for i in range(span)]
    eaten = [d["eaten"] for d in between if d and d["eaten"] is not None]
    if len(eaten) < MIN_LOGGED_SHARE * span:
        return {**not_yet, "message": f"Log your food on most days (only {len(eaten)} of the last {span}) "
                                      "so the estimates can adjust to you."}
    exercise = mean([(d or {}).get("exercise", 0) for d in between])

    # What you ate, minus what the scale says was stored (or plus what was used up), is what you burned
    real_burn = mean(eaten) - change * KCAL_PER_LB / span - exercise
    raw = real_burn / formula_burn
    trust = min(1.0, span / (2 * MIN_CALIBRATION_DAYS)) * min(1.0, len(eaten) / span)
    factor = 1 + (min(max(raw, FACTOR_LIMITS[0]), FACTOR_LIMITS[1]) - 1) * trust
    estimate = formula_burn * factor
    gap = estimate - formula_burn
    if abs(gap) < 50:
        message = f"Your weigh-ins match the estimate: you burn about {estimate:.0f} kcal a day."
    else:
        message = (f"From your weigh-ins and logs over {span} days, you seem to burn about {estimate:.0f} kcal a day, "
                   f"{abs(gap):.0f} {'more' if gap > 0 else 'less'} than the formula. The estimates below use that.")
    return {"factor": round(factor, 3), "burn_estimate": round(estimate), "days_used": span, "message": message}


def estimate_weight(weights: list, days: dict, base_burn: float, start_weight: float, start_date: date, today: date) -> dict:
    """
    Today's weight as the logs suggest: the latest smoothed weigh-in (or the start weight) plus the
    net calories logged since. Days with no food logged count as on plan (no change assumed beyond it).
    """
    if weights:
        anchor_day = weights[-1].date
        anchor = smoothed_weight(weights, anchor_day)
    else:
        anchor_day, anchor = start_date, start_weight
    net = 0.0
    day = anchor_day  # people weigh in in the morning, so that day's food comes after the weigh-in
    while day < today:  # today isn't over yet
        d = days.get(day)
        if d and d["eaten"] is not None:
            net += d["eaten"] - base_burn - d["exercise"]
        day += timedelta(days=1)
    return {
        "from_weight_lbs": anchor,
        "from_date": anchor_day,
        "estimated_weight_lbs": round(anchor + net / KCAL_PER_LB, 1),
    }


def goal_progress(goal, days: dict, base_burn: float, today: date, weights: list = (),
                  calorie_floor: float | None = None, max_rate_lbs: float | None = None) -> dict:
    """
    How the logged days add up against the plan, from the goal's start (or the last 4 weeks for a
    goal without a timeline) to yesterday. Only days with food logged count. For a timeline goal the
    count restarts at the latest weigh-in (`weights`, sorted by date), since that replanned the calories.
    Returns totals, a status, and for a timeline goal how many days earlier or later it should finish.
    status "unsafe_pace" (with a `warning`) when the logged days average under calorie_floor, or
    change weight faster than max_rate_lbs a week; it then gives no finish date.
    """
    start = goal.start_date or today - timedelta(days=28)
    since_weigh_in = False
    if goal.target_date:
        weigh_ins = [w.date for w in weights if start <= w.date <= today]
        if weigh_ins:
            start, since_weigh_in = weigh_ins[-1], True  # that day's food comes after the weigh-in
    sign = direction_sign(goal.goal_type)
    logged, ahead, eaten, net = 0, 0.0, 0.0, 0.0
    day = start
    while day < today:
        d = days.get(day)
        if d and d["eaten"] is not None:
            diff = d["eaten"] - d["exercise"] - goal.calorie_goal
            ahead += sign * diff if sign else diff
            eaten += d["eaten"]
            net += d["eaten"] - d["exercise"] - base_burn
            logged += 1
        day += timedelta(days=1)
    total_days = max(0, (today - start).days)

    warning = None
    if logged and calorie_floor and eaten / logged < calorie_floor:
        warning = (f"You have averaged {eaten / logged:.0f} kcal a day, under the safe minimum of "
                   f"{calorie_floor:.0f}. Eating more keeps you on a pace that lasts.")
    elif logged and sign and max_rate_lbs is not None and sign * net / logged * 7 / KCAL_PER_LB > max_rate_lbs + 0.05:
        pace = sign * net / logged * 7 / KCAL_PER_LB
        verb = "losing" if sign < 0 else "gaining"
        warning = (f"Your logs point to {verb} about {pace:.1f} lb a week, faster than the safe "
                   f"{max_rate_lbs:.1f}. Sticking closer to your calorie goal is safer.")

    result = {
        "since": start,
        "since_weigh_in": since_weigh_in,
        "days": total_days,
        "days_logged": logged,
        "ahead_kcal": round(ahead),
        "ahead_lbs": round(ahead / KCAL_PER_LB, 2),
        "status": "unsafe_pace" if warning else _status(ahead / logged, goal.goal_type) if logged else "not_logged",
        "warning": warning,
        "days_earlier": None,
        "projected_finish_date": None,
    }
    if goal.target_date and goal.goal_type in ("lose", "gain") and not warning:
        # The plan's daily change: from the planned pace, or what the calorie goal implies
        planned_daily = (goal.weekly_rate_lbs or 0) * KCAL_PER_LB / 7 or abs(goal.calorie_goal - base_burn)
        if planned_daily >= 50:
            days_earlier = math.floor(ahead / planned_daily) if ahead >= 0 else -math.ceil(-ahead / planned_daily)
            result["days_earlier"] = days_earlier
            result["projected_finish_date"] = max(today, goal.target_date - timedelta(days=days_earlier))
    return result


def progress_message(progress: dict, goal_type: str, today_logged: bool = False) -> str:
    """One friendly sentence for the progress card. today_logged: food is logged today, which only
    counts once the day is over."""
    n, status = progress["days_logged"], progress["status"]
    logged = f"{n} logged day{'s' if n != 1 else ''}"
    if status == "unsafe_pace":
        return progress["warning"]
    if not n:
        if today_logged:
            return "Today's meals count once the day is over. Check back tomorrow to see how your days add up."
        if progress.get("since_weigh_in"):
            return "Your weigh-in updated your plan. Log what you eat to see how the next days add up."
        return "Log what you eat to see how your days add up toward your goal."
    kcal, lbs = abs(progress["ahead_kcal"]), abs(progress["ahead_lbs"])
    days = progress["days_earlier"]
    when = ""
    if days:
        when = f" At this rate you finish about {abs(days)} day{'s' if abs(days) != 1 else ''} {'early' if days > 0 else 'late'}."
    if goal_type == "maintain":
        if status == "on_track":
            return f"Your {logged} {'are' if n != 1 else 'is'} close to your goal. Nice and steady."
        return f"Your {logged} come{'s' if n == 1 else ''} to {kcal} kcal {'over' if status == 'over' else 'under'} your goal (about {lbs:.1f} lb)."
    if progress.get("since_weigh_in"):
        logged += " since your weigh-in"
    if status == "ahead":
        return f"You are {kcal} kcal ahead of plan over {logged}, about {lbs:.1f} lb.{when}"
    if status == "behind":
        return f"You are {kcal} kcal behind plan over {logged}, about {lbs:.1f} lb.{when} One day at a time."
    return f"Right on plan over {logged}.{when}"
