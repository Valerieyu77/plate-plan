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

    How it works (a beam search): start with the empty plate. Add one dish to it in every way that
    helps, keep the BEAM best plates, add one more dish to each of those, and so on up to
    MAX_DISHES. The answer is the best plate seen along the way. The same inputs always give the
    same plate.
    """
    menu = [i for i in items if (i.get("kcal") or 0) >= MIN_KCAL] or [i for i in items if (i.get("kcal") or 0) > 0]
    if not menu:
        return _result([], target, "No dishes on this menu fit your restrictions.")
    if all(target[k] <= 0 for k in NUTRIENTS):
        return _result([], target, "You have already reached your target for this meal.")

    avoid = set(avoid_ids)
    max_steps = int(max_servings / STEP)
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
        n = max(0, min(max_steps, round(along / length[i])))
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

    best, beam = {}, [{}]
    for _ in range(MAX_DISHES):
        grown = []
        for plate in beam:
            gap, base = gap_of(plate), cost(plate)
            for i in range(len(menu)):
                if i not in plate:
                    n, saved = fit(gap, i)
                    if n:
                        grown.append((base - saved, plate, i, n))
        closest = heapq.nsmallest(BEAM, grown, key=lambda g: g[0])
        beam = list({tuple(sorted(p.items())): p for p in (refit({**plate, i: n}) for _, plate, i, n in closest)}.values())
        if not beam:
            break
        best = min([best, *beam], key=cost)

    lines = [
        {"item_id": menu[i].get("id"), "name": menu[i].get("name"), "servings": n * STEP,
         **{k: round(n * STEP * (menu[i].get(k) or 0), 1) for k in NUTRIENTS}}
        for i, n in best.items()
    ]
    lines.sort(key=lambda line: -line["kcal"])
    return _result(lines, target)


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
