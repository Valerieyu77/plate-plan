"""
D's part: choose dishes for one meal.

This is a plain function. It does NOT read files or the database: the caller hands it everything.
That way it works the same on the sample JSON file now and on the live menu later.

How to try it (no database needed), from Project/backend:
    python -m app.try_recommend                       # uses data/menu_sample.json
    python -m app.try_recommend --meal dinner --kcal 700
How to check your work:
    python -m pytest tests/test_recommend.py
"""

import heapq
import math
import re

NUTRIENTS = ["kcal", "protein_g", "carbs_g", "fat_g"]
LABELS = {"kcal": "calories", "protein_g": "protein", "carbs_g": "carbs", "fat_g": "fat"}

STEP = 0.5        # servings move in half steps
MAX_DISHES = 5    # a plate, not a buffet
MIN_KCAL = 20     # garnishes and condiments are not worth recommending
TOLERANCE = 0.10  # within 10% of every nutrient counts as a match (no note)
BEAM = 150        # how many of the best plates are kept each time a dish is added

# The cost of a plate is the sum over nutrients of WEIGHT * (share of the target missed) squared,
# so one big miss is worse than several small ones. Lower is better.
WEIGHTS = {"kcal": 2.0, "protein_g": 1.5, "carbs_g": 1.0, "fat_g": 1.0}
# A miss is measured as a share of the target, but never of less than this (a target near 0 would blow it up)
FLOORS = {"kcal": 50.0, "protein_g": 5.0, "carbs_g": 5.0, "fat_g": 5.0}
DISH_COST = 0.005  # added per dish, so a dish must earn its place: 3 dishes beat 5 when equally close
AVOID_COST = 0.05  # added for a dish in avoid_ids, so it is only used when it is clearly the better choice

# Rules that make a plate look like a meal. Matching the numbers alone would happily use sauces and
# herbs (low calories, easy to fine-tune with) or half a tortilla to close a small gap.
MIN_LINE_KCAL = 80      # a dish on the plate must add at least this much
MIN_DISHES = 2          # a normal-size meal is more than one dish
NORMAL_MEAL_KCAL = 350  # ...where "normal size" means a target of at least this many kcal
DESSERT_STEPS = 2       # at most one dessert, and at most one serving of it (2 half steps)
_NOT_A_MEAL = re.compile(
    r"\b(sauce|dressing|syrup|ketchup|mayonnaise|mustard|gravy|jelly|creamer|seasoning|topping|relish)\b", re.I
)
_NOT_A_MEAL_CATEGORY = ("sauce", "dressing", "condiment", "beverage", "topping")


def _is_meal_dish(item: dict) -> bool:
    """False for sauces, dressings, condiments, toppings and drinks: they are not a meal."""
    if _NOT_A_MEAL.search(item.get("name") or ""):
        return False
    category = (item.get("category") or "").lower()
    return not any(word in category for word in _NOT_A_MEAL_CATEGORY)


def _is_dessert(item: dict) -> bool:
    return "dessert" in (item.get("category") or "").lower()


def recommend(target: dict, items: list[dict], max_servings: float = 3.0, avoid_ids=()) -> dict:
    """
    Pick dishes (and how many servings of each) so the meal's nutrients are as close as possible
    to `target`.

    target: {"kcal": 600, "protein_g": 45, "carbs_g": 60, "fat_g": 17}
        what this meal should provide. (B's code works this out; you can just use it.)

    items: a list of dishes the user is allowed to eat, each a dict with at least
        {"id": 1234, "name": "Grilled Chicken",
         "kcal": 300, "protein_g": 40, "carbs_g": 2, "fat_g": 12,      # all per ONE serving
         "serving_unit": "Each", "serving_grams": 120}                  # how big one serving is
        (the real menu items have more fields; ignore the ones you don't need)

    max_servings: the most servings of any single dish (so you don't get "9 servings of chicken").

    avoid_ids: ids of dishes to steer away from, e.g. ones eaten recently (for variety).

    Returns:
        {
          "items":  [{"item_id": 1234, "name": "Grilled Chicken", "servings": 1.5,
                      "kcal": 450, "protein_g": 60, "carbs_g": 3, "fat_g": 18}, ...],   # totals for that line
          "total":  {"kcal": 610, "protein_g": 45, "carbs_g": 60, "fat_g": 18},          # sum of the lines
          "target": {...the same target that was passed in...},
          "note":   None,   # or a short sentence when there is no exact match, e.g. "Closest option: 5% under on protein."
        }

    Rules on top of the numbers (see MIN_LINE_KCAL and friends): no sauces, dressings, condiments,
    toppings or drinks; every dish adds at least MIN_LINE_KCAL; at most one dessert, one serving of
    it; a normal-size meal has at least MIN_DISHES dishes.

    How it works (a beam search): start with the empty plate. Add one dish to it in every way that
    helps, keep the BEAM best plates, add one more dish to each of those, and so on up to
    MAX_DISHES. The answer is the best plate seen along the way. The same inputs always give the
    same plate.
    """
    max_steps = int(max_servings / STEP)

    def cap_of(item):  # most half servings of this dish
        return DESSERT_STEPS if _is_dessert(item) else max_steps

    def worth_it(item):  # a real dish, and one that can reach MIN_LINE_KCAL within its serving limit
        kcal = item.get("kcal") or 0
        return kcal >= MIN_KCAL and _is_meal_dish(item) and kcal * STEP * cap_of(item) >= MIN_LINE_KCAL

    menu, seen = [], set()
    for item in items:
        name = (item.get("name") or "").strip().lower()
        if worth_it(item) and name not in seen:  # the same dish listed at two stations counts once
            seen.add(name)
            menu.append(item)
    # If the rules leave nothing (a menu of only sauces and sides), fall back to anything with calories
    menu = menu or [i for i in items if (i.get("kcal") or 0) >= MIN_KCAL] or [i for i in items if (i.get("kcal") or 0) > 0]
    if not menu:
        return _result([], target, "No dishes on this menu fit your restrictions.")
    if all(target[k] <= 0 for k in NUTRIENTS):
        return _result([], target, "You have already reached your target for this meal.")

    avoid = set(avoid_ids)
    cap = [cap_of(i) for i in menu]
    dessert = [_is_dessert(i) for i in menu]
    # Smallest number of half servings that makes a dish worth putting on the plate
    min_n = [min(cap[k], max(1, math.ceil(MIN_LINE_KCAL / ((i.get("kcal") or 1) * STEP)))) for k, i in enumerate(menu)]
    # Rescale every nutrient so that cost = (distance from goal) squared: then the best amount of a
    # dish can be worked out directly instead of trying each amount.
    scale = [WEIGHTS[k] ** 0.5 / max(target[k], FLOORS[k]) for k in NUTRIENTS]
    goal = [s * target[k] for s, k in zip(scale, NUTRIENTS)]
    half = [[s * STEP * (i.get(k) or 0) for s, k in zip(scale, NUTRIENTS)] for i in menu]  # one half serving
    length = [sum(x * x for x in h) for h in half]
    extra = [DISH_COST + (AVOID_COST if i.get("id") in avoid else 0) for i in menu]

    # A plate is {index in menu: number of half servings}
    def gap_of(plate):
        return [g - sum(n * half[i][k] for i, n in plate.items()) for k, g in enumerate(goal)]

    def cost(plate):
        return sum(x * x for x in gap_of(plate)) + sum(extra[i] for i in plate)

    def fit(gap, i):
        """Best number of half servings of dish i to fill `gap`, and how much that lowers the cost.
        (0, 0) when the dish does not help enough to be worth adding."""
        along = sum(g * x for g, x in zip(gap, half[i]))
        n = max(0, min(cap[i], round(along / length[i])))
        if n and n < min_n[i]:
            n = min_n[i]  # either a meaningful amount of the dish, or none of it
        saved = 2 * n * along - n * n * length[i] - extra[i]
        return (n, saved) if n and saved > 0 else (0, 0)

    def refit(plate):
        """Adding a dish changes what the others should be: re-fit each one until nothing moves."""
        for _ in range(10):
            before = plate
            for i in list(plate):
                rest = {j: n for j, n in plate.items() if j != i}
                n, _ = fit(gap_of(rest), i)
                plate = {**rest, i: n} if n else rest
            if plate == before:
                break
        return plate

    need = MIN_DISHES if target["kcal"] >= NORMAL_MEAL_KCAL and len(menu) >= MIN_DISHES else 1
    best, best_enough, beam = {}, None, [{}]
    for _ in range(MAX_DISHES):
        grown = []
        for plate in beam:
            gap, base = gap_of(plate), cost(plate)
            has_dessert = any(dessert[j] for j in plate)
            for i in range(len(menu)):
                if i not in plate and not (dessert[i] and has_dessert):
                    n, saved = fit(gap, i)
                    if n:
                        grown.append((base - saved, plate, i, n))
        closest = heapq.nsmallest(BEAM, grown, key=lambda g: g[0])
        beam = list({tuple(sorted(p.items())): p for p in (refit({**plate, i: n}) for _, plate, i, n in closest)}.values())
        if not beam:
            break
        best = min([best, *beam], key=cost)
        for plate in beam:  # the best plate that has enough dishes to be a meal
            if len(plate) >= need and (best_enough is None or cost(plate) < cost(best_enough)):
                best_enough = plate
    best = best_enough if best_enough is not None else best

    lines = [
        {"item_id": menu[i].get("id"), "name": menu[i].get("name"), "servings": n * STEP,
         **{k: round(n * STEP * (menu[i].get(k) or 0), 1) for k in NUTRIENTS}}
        for i, n in best.items()
    ]
    lines.sort(key=lambda line: -line["kcal"])
    return _result(lines, target)


WORKOUT_FOCUS = {"lose": "cardio", "maintain": "mixed", "gain": "strength"}
WORKOUT_MINUTES = {"light": 20, "moderate": 35, "hard": 50}
SURPLUS_KCAL = 200  # eating this much over the goal calls for a harder session (and this much under, an easier one)


def recommend_workout(goal_type: str, calorie_goal: float, kcal_eaten: float) -> dict:
    """
    Suggest a workout for today from the user's goal and how much they have eaten so far.

    goal_type: "lose", "maintain" or "gain" (see GOAL_TYPES in models.py)
    calorie_goal: the user's daily calorie goal
    kcal_eaten: calories eaten today

    Returns:
        {
          "focus":     "cardio" | "mixed" | "strength",
          "intensity": "light" | "moderate" | "hard",
          "minutes":   35,
          "exercises": [],   # TODO: fill in with {"name": ..., "sets": ..., "reps": ..., "minutes": ...}
          "note":      "You are 300 kcal over your goal: a harder session today.",
        }

    This is a template: it picks the kind of session, but the exercises themselves are left empty
    for now (see _exercises_for).
    """
    focus = WORKOUT_FOCUS.get(goal_type, "mixed")
    balance = kcal_eaten - calorie_goal  # > 0 means over the goal

    if balance > SURPLUS_KCAL:
        intensity = "hard"
        note = f"You are {balance:.0f} kcal over your goal: a harder session today."
    elif balance < -SURPLUS_KCAL:
        # Training hard on an empty tank is a bad idea, and someone trying to gain needs those calories
        intensity = "light"
        note = f"You are {-balance:.0f} kcal under your goal: keep it light and eat enough today."
    else:
        intensity = "moderate"
        note = None

    return {
        "focus": focus,
        "intensity": intensity,
        "minutes": WORKOUT_MINUTES[intensity],
        "exercises": _exercises_for(focus, intensity),
        "note": note,
    }


def _exercises_for(focus: str, intensity: str) -> list[dict]:
    """TODO: return the actual exercises for this kind of session, e.g.
    [{"name": "Squats", "sets": 3, "reps": 10}, {"name": "Jog", "minutes": 20}]"""
    return []


def _result(lines: list[dict], target: dict, note: str | None = None) -> dict:
    total = {k: round(sum(line[k] for line in lines), 1) for k in NUTRIENTS}
    if note is None:
        note = _miss_note(total, target) if lines else "No dishes on this menu fit your restrictions."
    return {"items": lines, "total": total, "target": target, "note": note}


def _miss_note(total: dict, target: dict) -> str | None:
    """None when every nutrient is within TOLERANCE of the target; otherwise name the biggest miss."""
    miss = {k: (total[k] - target[k]) / max(target[k], FLOORS[k]) for k in NUTRIENTS}
    worst = max(NUTRIENTS, key=lambda k: abs(miss[k]))
    if abs(miss[worst]) <= TOLERANCE:
        return None
    return f"Closest option: {abs(miss[worst]):.0%} {'over' if miss[worst] > 0 else 'under'} on {LABELS[worst]}."
