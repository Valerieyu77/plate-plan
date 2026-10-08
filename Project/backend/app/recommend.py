"""
D's part: choose dishes for one meal.   >>> FILL IN recommend() BELOW <<<

This is a plain function. It does NOT read files or the database: the caller hands it everything.
That way it works the same on the sample JSON file now and on the live menu later.

How to try it (no database needed), from Project/backend:
    python -m app.try_recommend                       # uses data/menu_sample.json
    python -m app.try_recommend --meal dinner --kcal 700
How to check your work:
    python -m pytest tests/test_recommend.py          # remove the @skip lines as you finish each part
"""

NUTRIENTS = ["kcal", "protein_g", "carbs_g", "fat_g"]


def recommend(target: dict, items: list[dict], max_servings: float = 3.0) -> dict:
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

    Returns:
        {
          "items":  [{"item_id": 1234, "name": "Grilled Chicken", "servings": 1.5,
                      "kcal": 450, "protein_g": 60, "carbs_g": 3, "fat_g": 18}, ...],   # totals for that line
          "total":  {"kcal": 610, "protein_g": 45, "carbs_g": 60, "fat_g": 18},          # sum of the lines
          "target": {...the same target that was passed in...},
          "note":   None,   # or a short sentence when there is no exact match, e.g. "Closest option: 5% under on protein."
        }

    Ideas, in the order to do them:
      1. Simplest thing that works: pick a few dishes and half/whole servings so totals are close to target.
      2. Use PuLP (pip install pulp) to do it properly: servings are variables (steps of 0.5), minimise
         how far the totals are from the target.
      3. Variety: don't always return the same dishes (e.g. add a little randomness, or avoid a dish
         the caller says was eaten recently).
      4. If the target cannot be hit (menu too small), return the closest option and explain in `note`.
    """
    raise NotImplementedError("recommend() is not written yet. Open app/recommend.py and fill it in.")
