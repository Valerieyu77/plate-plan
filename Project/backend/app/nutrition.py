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


def daily_targets(user, goal_type: str, today: date | None = None) -> dict:
    """
    Returns calorie_goal, protein_goal_g, carb_goal_g, fat_goal_g and a warning (or None).
    Raises ValueError if the profile is incomplete or the goal type is unknown.
    """
    if goal_type not in GOAL_OFFSETS:
        raise ValueError(f"goal_type must be one of {list(GOAL_OFFSETS)}")
    missing = missing_profile_fields(user)
    if missing:
        raise ValueError(f"profile is missing: {', '.join(missing)}")

    age = age_from_birthdate(user.birthdate, today)
    factor = ACTIVITY_FACTORS.get(user.activity_level or DEFAULT_ACTIVITY, ACTIVITY_FACTORS[DEFAULT_ACTIVITY])
    tdee = bmr(user.weight_lbs, user.height_in, age, user.gender) * factor

    calories = tdee + GOAL_OFFSETS[goal_type]
    floor = MIN_CALORIES.get((user.gender or "").strip().lower(), DEFAULT_MIN_CALORIES)
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
