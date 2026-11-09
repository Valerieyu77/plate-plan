"""
Baseline daily-target calculation (prototype). Plain functions, no database access.
B can replace or extend this: per-meal split, safety limits, cross-meal adjustment, progress.

Inputs use the same units as the User table: weight in lbs, height in inches.
"""

from datetime import date

LBS_PER_KG = 2.20462
CM_PER_INCH = 2.54

# Multiplies BMR to get total daily energy expenditure
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
DEFAULT_ACTIVITY = "light"  # used when the user didn't give one

# Daily calorie change per goal; matches the frontend design (-450 / 0 / +400)
GOAL_OFFSETS = {"lose": -450, "maintain": 0, "gain": 400}

# Protein in grams per kg of body weight, per goal
PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}

FAT_CALORIE_SHARE = 0.25
MIN_CALORIES = {"male": 1500, "female": 1200}  # never go below this
DEFAULT_MIN_CALORIES = 1350

REQUIRED_FIELDS = ["weight_lbs", "height_in", "gender", "birthdate"]

# The youngest age the app is for: the Mifflin-St Jeor formula behind daily_targets() is made for adults.
# The sign-up form has the same limit (MIN_AGE in frontend/src/pages/AuthPage.jsx).
MIN_AGE = 16


def age_from_birthdate(birthdate: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def missing_profile_fields(user) -> list[str]:
    return [f for f in REQUIRED_FIELDS if getattr(user, f, None) in (None, "")]


def bmr(weight_lbs: float, height_in: float, age: int, gender: str) -> float:
    """Mifflin-St Jeor equation. Unknown genders use the midpoint of the male/female constants."""
    kg = weight_lbs / LBS_PER_KG
    cm = height_in * CM_PER_INCH
    constant = {"male": 5, "female": -161}.get((gender or "").strip().lower(), -78)
    return 10 * kg + 6.25 * cm - 5 * age + constant


def tdee(user, today: date | None = None) -> float:
    """Calories burned per day (BMR x activity factor). The profile must be complete."""
    age = age_from_birthdate(user.birthdate, today)
    factor = ACTIVITY_FACTORS.get(user.activity_level or DEFAULT_ACTIVITY, ACTIVITY_FACTORS[DEFAULT_ACTIVITY])
    return bmr(user.weight_lbs, user.height_in, age, user.gender) * factor


def calorie_floor(user) -> int:
    return MIN_CALORIES.get((user.gender or "").strip().lower(), DEFAULT_MIN_CALORIES)


def daily_targets(user, goal_type: str, today: date | None = None, calorie_offset: float | None = None) -> dict:
    """
    Returns calorie_goal, protein_goal_g, carb_goal_g, fat_goal_g and a warning (or None).
    calorie_offset replaces the goal type's fixed offset (a timeline goal sets its own; see timeline.py).
    Raises ValueError if the profile is incomplete or the goal type is unknown.
    """
    if goal_type not in GOAL_OFFSETS:
        raise ValueError(f"goal_type must be one of {list(GOAL_OFFSETS)}")
    missing = missing_profile_fields(user)
    if missing:
        raise ValueError(f"profile is missing: {', '.join(missing)}")

    offset = GOAL_OFFSETS[goal_type] if calorie_offset is None else calorie_offset
    calories = tdee(user, today) + offset
    floor = calorie_floor(user)
    warning = None
    if calories < floor:
        calories = floor
        warning = f"Target raised to the safe minimum of {floor} kcal/day."

    protein_g = PROTEIN_G_PER_KG[goal_type] * user.weight_lbs / LBS_PER_KG
    fat_g = FAT_CALORIE_SHARE * calories / 9
    carb_g = max(0.0, (calories - 4 * protein_g - 9 * fat_g) / 4)

    return {
        "calorie_goal": round(calories),
        "protein_goal_g": round(protein_g),
        "carb_goal_g": round(carb_g),
        "fat_goal_g": round(fat_g),
        "warning": warning,
    }


# ---------- Per-meal targets, cross-meal adjustment, progress ----------

NUTRIENTS = ["kcal", "protein_g", "carbs_g", "fat_g"]

# Meals map to a slot of the day. Light lunch and lunch share the midday slot (a hall serves one or the other).
MEAL_SLOT = {
    "breakfast": 0,
    "light lunch": 1, "lunch": 1, "kosher lunch": 1,
    "dinner": 2, "kosher dinner": 2,
}
# What the user thinks of as a meal. Light lunch / kosher lunch are shown under "lunch" in the UI;
# the data itself keeps the site's own menu names (they are never merged in the database).
MEAL_GROUP = {
    "breakfast": "breakfast",
    "light lunch": "lunch", "lunch": "lunch", "kosher lunch": "lunch",
    "dinner": "dinner", "kosher dinner": "dinner",
}
GROUP_ORDER = ["breakfast", "lunch", "dinner"]
# Order of the site's menu names within a day, earliest first
MEAL_ORDER = ["breakfast", "light lunch", "lunch", "kosher lunch", "dinner", "kosher dinner"]


def meals_in_group(name: str) -> list[str]:
    """'lunch' -> ['light lunch', 'lunch', 'kosher lunch']; a raw name like 'light lunch' -> itself."""
    key = name.strip().lower()
    if key in GROUP_ORDER:
        return [m for m in MEAL_ORDER if MEAL_GROUP[m] == key]
    return [key]


# Share of the day's food for each slot, when all three are still ahead
SLOT_WEIGHT = {0: 0.25, 1: 0.35, 2: 0.40}


def zero_nutrients() -> dict:
    return {k: 0.0 for k in NUTRIENTS}


def add_nutrients(a: dict, b: dict, times: float = 1.0) -> dict:
    return {k: a[k] + times * b[k] for k in NUTRIENTS}


def goal_to_targets(goal) -> dict:
    """A Goal row -> {kcal, protein_g, carbs_g, fat_g}; unset values count as 0."""
    return {
        "kcal": goal.calorie_goal or 0,
        "protein_g": goal.protein_goal_g or 0,
        "carbs_g": goal.carb_goal_g or 0,
        "fat_g": goal.fat_goal_g or 0,
    }


def item_nutrients(item, servings: float) -> dict:
    """Nutrients of `servings` servings of a menu item (menu values are per ONE serving)."""
    return {k: servings * (getattr(item, k) or 0) for k in NUTRIENTS}


def _fit_macros_to_calories(target: dict) -> dict:
    """
    Make protein/carbs/fat fit inside the calories left (e.g. 235 kcal left but 120 g protein +
    142 g carbs + 41 g fat would need about 1400 kcal). Protein is kept first because it is the
    macro people are trying to hit; carbs and fat are scaled down, keeping their ratio, to fill
    the calories that remain. So the three macros never need more calories than the target.
    """
    kcal = target["kcal"]
    if kcal <= 0:
        return {k: 0.0 for k in NUTRIENTS}
    protein, carbs, fat = target["protein_g"], target["carbs_g"], target["fat_g"]
    if 4 * protein + 4 * carbs + 9 * fat <= kcal:
        return dict(target)
    if 4 * protein >= kcal:  # not even the protein fits: use all calories for protein
        return {"kcal": kcal, "protein_g": kcal / 4, "carbs_g": 0.0, "fat_g": 0.0}
    factor = (kcal - 4 * protein) / (4 * carbs + 9 * fat)
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs * factor, "fat_g": fat * factor}


def meal_target(daily: dict, consumed_by_meal: dict[str, dict], meal: str, meals_eaten: list[str] | None = None) -> dict:
    """
    How much is left to eat at `meal`, given what was already logged today.

    daily:            {kcal, protein_g, carbs_g, fat_g} for the whole day
    consumed_by_meal: {meal name: nutrients eaten at that meal so far today}

    What was eaten at other meals is subtracted from the day. The rest is shared between this
    meal and every slot of the day that has nothing logged yet, by SLOT_WEIGHT. A slot with no
    log counts as still to come, because the user may simply not have logged it; so at dinner with
    nothing logged you get dinner's 40% of the day, not the whole day. Anything already logged at
    this slot is subtracted again, so a half-logged lunch asks for the rest of lunch. Finally the
    macros are scaled so they never need more calories than the calorie target.

    meals_eaten: the meals this user eats each day ("breakfast", "lunch", "dinner"); None for all
    three. Only those count as still to come, so someone who skips lunch shares the day between
    breakfast and dinner (25:40, about 38% and 62%) and gets bigger plates. The meal asked about always
    counts, so a lunch eaten on a day off from the routine still gets its share.
    Returns {"target": ..., "meal_budget": ..., "consumed_this_meal": ..., "remaining_day": ...}.
    """
    key = meal.strip().lower()
    if key not in MEAL_SLOT:
        raise ValueError(f"unknown meal '{meal}'; expected one of {sorted(MEAL_SLOT)}")
    slot = MEAL_SLOT[key]

    consumed_here = zero_nutrients()
    consumed_other = zero_nutrients()
    logged_slots = set()  # slots other than this one that have something logged
    for name, nutrients in consumed_by_meal.items():
        other_slot = MEAL_SLOT.get(name.strip().lower())
        if other_slot == slot:
            consumed_here = add_nutrients(consumed_here, nutrients)
        else:
            consumed_other = add_nutrients(consumed_other, nutrients)
            if other_slot is not None and any(nutrients[k] > 0 for k in NUTRIENTS):
                logged_slots.add(other_slot)

    planned = {MEAL_SLOT[m] for m in meals_eaten} if meals_eaten else set(SLOT_WEIGHT)
    pending = [s for s in SLOT_WEIGHT if s == slot or (s in planned and s not in logged_slots)]
    share = SLOT_WEIGHT[slot] / sum(SLOT_WEIGHT[s] for s in pending)

    budget, target = {}, {}
    for k in NUTRIENTS:
        budget[k] = max(0.0, daily[k] - consumed_other[k]) * share
        target[k] = max(0.0, budget[k] - consumed_here[k])
    target = _fit_macros_to_calories(target)
    total_eaten = add_nutrients(consumed_here, consumed_other)
    return {
        "target": {k: round(v, 1) for k, v in target.items()},
        "meal_budget": {k: round(v, 1) for k, v in budget.items()},
        "consumed_this_meal": {k: round(v, 1) for k, v in consumed_here.items()},
        "remaining_day": {k: round(max(0.0, daily[k] - total_eaten[k]), 1) for k in NUTRIENTS},
    }


def day_progress(daily: dict, consumed: dict) -> dict:
    """Target vs actual for a day. `remaining` never goes below 0 (going over shows in `over`)."""
    return {
        "target": {k: round(daily[k], 1) for k in NUTRIENTS},
        "actual": {k: round(consumed[k], 1) for k in NUTRIENTS},
        "remaining": {k: round(max(0.0, daily[k] - consumed[k]), 1) for k in NUTRIENTS},
        "over": {k: round(max(0.0, consumed[k] - daily[k]), 1) for k in NUTRIENTS},
    }
