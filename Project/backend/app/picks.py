"""
Pure helpers for "Today's best picks": how well a hall's best plate matches what the user still needs,
and what a high-protein plate looks like. No database access here; the endpoint in main.py gathers
the menus and calls recommend().
"""

from .recommend import FLOORS, NUTRIENTS, WEIGHTS

# A high-protein plate aims at this share of its calories from protein, carbs and fat
HIGH_PROTEIN_SHARE = {"protein_g": 0.40, "carbs_g": 0.35, "fat_g": 0.25}
KCAL_PER_GRAM = {"protein_g": 4.0, "carbs_g": 4.0, "fat_g": 9.0}


def match_score(target: dict, total: dict) -> int:
    """
    0 to 100: how close a plate gets to the target on all four nutrients. 100 means every number is
    on target; a nutrient that is off by 100% or more counts as fully missed. Calories and protein
    count more, using the same weights the recommender optimises for.
    """
    if not total or all(total.get(k, 0) <= 0 for k in NUTRIENTS):
        return 0
    misses = {k: min(1.0, abs(total[k] - target[k]) / max(target[k], FLOORS[k])) for k in NUTRIENTS}
    weighted = sum(WEIGHTS[k] * misses[k] for k in NUTRIENTS) / sum(WEIGHTS.values())
    return round(100 * (1 - weighted))


def high_protein_target(kcal: float) -> dict:
    """The target for a high-protein plate on a calorie budget: 40% of calories from protein, 35% carbs, 25% fat."""
    target = {"kcal": float(kcal)}
    for k, share in HIGH_PROTEIN_SHARE.items():
        target[k] = round(kcal * share / KCAL_PER_GRAM[k], 1)
    return target


def protein_share(total: dict) -> int:
    """Percent of a plate's calories that come from protein."""
    kcal = total.get("kcal") or 0
    return round(100 * 4 * (total.get("protein_g") or 0) / kcal) if kcal > 0 else 0
