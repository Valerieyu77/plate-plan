"""
Checks for recommend() and recommend_workout().
Run:  python -m pytest tests/test_recommend.py
"""
import json
import time
from pathlib import Path

import pytest

from app.recommend import NUTRIENTS, SURPLUS_KCAL, recommend, recommend_workout

TARGET = {"kcal": 600, "protein_g": 40, "carbs_g": 60, "fat_g": 20}
MENU = [
    {"id": 1, "name": "Chicken", "kcal": 300, "protein_g": 40, "carbs_g": 2, "fat_g": 12},
    {"id": 2, "name": "Rice", "kcal": 200, "protein_g": 4, "carbs_g": 44, "fat_g": 1},
    {"id": 3, "name": "Salad", "kcal": 80, "protein_g": 3, "carbs_g": 10, "fat_g": 4},
    {"id": 4, "name": "Cookie", "kcal": 170, "protein_g": 2, "carbs_g": 22, "fat_g": 8},
]


def test_result_has_the_agreed_shape():
    r = recommend(TARGET, MENU)
    assert set(r) >= {"items", "total", "target", "note"}
    assert r["target"] == TARGET
    for line in r["items"]:
        assert set(line) >= {"item_id", "name", "servings", *NUTRIENTS}


def test_total_is_the_sum_of_the_lines():
    r = recommend(TARGET, MENU)
    for k in NUTRIENTS:
        assert r["total"][k] == pytest.approx(sum(line[k] for line in r["items"]))


def test_gets_close_to_a_reachable_target():
    r = recommend(TARGET, MENU)
    assert abs(r["total"]["kcal"] - TARGET["kcal"]) <= 0.1 * TARGET["kcal"]


def test_never_exceeds_max_servings():
    r = recommend(TARGET, MENU, max_servings=2)
    assert all(line["servings"] <= 2 for line in r["items"])


def test_unreachable_target_returns_closest_with_a_note():
    r = recommend({"kcal": 5000, "protein_g": 300, "carbs_g": 500, "fat_g": 100}, MENU[:1], max_servings=1)
    assert r["items"] and r["note"]


def test_servings_are_half_steps():
    r = recommend(TARGET, MENU)
    assert all(line["servings"] > 0 and line["servings"] % 0.5 == 0 for line in r["items"])


def test_avoid_ids_steers_away_from_a_dish():
    twin = {**MENU[0], "id": 5, "name": "Turkey"}
    assert "Chicken" in [line["name"] for line in recommend(TARGET, MENU + [twin])["items"]]
    names = [line["name"] for line in recommend(TARGET, MENU + [twin], avoid_ids=[1])["items"]]
    assert "Turkey" in names and "Chicken" not in names


def test_empty_menu_and_met_target_return_no_dishes_with_a_note():
    assert recommend(TARGET, [])["items"] == [] and recommend(TARGET, [])["note"]
    done = recommend({k: 0 for k in NUTRIENTS}, MENU)
    assert done["items"] == [] and done["note"]


# ---------- rules that make a plate look like a meal ----------

from app.recommend import MIN_LINE_KCAL  # noqa: E402

RULES_MENU = MENU + [
    {"id": 6, "name": "Fresh Cilantro", "kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "category": "Toppings"},
    {"id": 7, "name": "Ranch Dressing", "kcal": 140, "protein_g": 0, "carbs_g": 2, "fat_g": 15, "category": "Dressings & Condiments"},
    {"id": 8, "name": "Soy Sauce", "kcal": 60, "protein_g": 2, "carbs_g": 5, "fat_g": 0, "category": "Entrees"},
    {"id": 9, "name": "Brownie", "kcal": 220, "protein_g": 3, "carbs_g": 30, "fat_g": 10, "category": "Desserts"},
    {"id": 10, "name": "Fruit Cup", "kcal": 60, "protein_g": 1, "carbs_g": 15, "fat_g": 0, "category": "Fruits"},
]
for _m in RULES_MENU[:4]:
    _m.setdefault("category", "Entrees")
RULES_MENU[3]["category"] = "Desserts"  # the Cookie


def test_skips_sauces_dressings_and_herbs():
    names = {line["name"] for line in recommend(TARGET, RULES_MENU)["items"]}
    assert not names & {"Fresh Cilantro", "Ranch Dressing", "Soy Sauce"}


def test_at_most_one_dessert_and_one_serving_of_it():
    for target in (TARGET, {"kcal": 900, "protein_g": 20, "carbs_g": 150, "fat_g": 40}):
        lines = [l for l in recommend(target, RULES_MENU)["items"] if l["name"] in {"Cookie", "Brownie"}]
        assert len(lines) <= 1 and all(l["servings"] <= 1 for l in lines)


def test_every_dish_adds_a_meaningful_amount():
    for line in recommend(TARGET, RULES_MENU)["items"]:
        assert line["kcal"] >= MIN_LINE_KCAL - 1


def test_a_normal_meal_has_at_least_two_dishes():
    assert len(recommend(TARGET, RULES_MENU)["items"]) >= 2


def test_a_menu_of_only_sauces_still_returns_something_rather_than_nothing():
    sauces = [m for m in RULES_MENU if m["id"] in (7, 8)]
    assert recommend({"kcal": 200, "protein_g": 5, "carbs_g": 20, "fat_g": 10}, sauces)["items"]


def test_duplicate_dish_names_count_once():
    names = [l["name"] for l in recommend(TARGET, RULES_MENU + [dict(RULES_MENU[0], id=99)])["items"]]
    assert names.count("Chicken") <= 1


SAMPLE = Path(__file__).resolve().parent.parent / "data" / "menu_sample.json"


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample menu not in the repo")
def test_real_menus_give_plates_that_look_like_meals_and_hit_the_target():
    data = json.loads(SAMPLE.read_text())
    menus = {}
    for i in data:
        menus.setdefault((i["hall"], i["date"], i["meal"]), []).append(dict(i, id=i["source_id"]))
    big = [(k, v) for k, v in sorted(menus.items()) if len(v) >= 8][::3]
    assert len(big) >= 8
    target = {"kcal": 600, "protein_g": 45, "carbs_g": 65, "fat_g": 18}
    close, start = 0, time.time()
    for key, items in big:
        by_id = {i["id"]: i for i in items}
        lines = recommend(dict(target), items)["items"]
        assert 2 <= len(lines) <= 5, key
        assert all(l["kcal"] >= MIN_LINE_KCAL - 1 for l in lines), key
        assert sum("dessert" in (by_id[l["item_id"]].get("category") or "").lower() for l in lines) <= 1, key
        assert not any(w in (by_id[l["item_id"]].get("category") or "").lower() for l in lines for w in ("sauce", "dressing", "condiment", "beverage")), key
        total = {k: sum(l[k] for l in lines) for k in NUTRIENTS}
        close += all(abs(total[k] - target[k]) <= 0.15 * target[k] for k in NUTRIENTS)
    assert close >= 0.8 * len(big)  # most plates land within 15% on every nutrient
    assert (time.time() - start) / len(big) < 0.5  # seconds per menu


# ---------- recommend_workout() ----------

def test_workout_has_the_agreed_shape():
    w = recommend_workout("maintain", 2000, 2000)
    assert set(w) >= {"focus", "intensity", "minutes", "exercises", "note"}
    assert isinstance(w["exercises"], list)


@pytest.mark.parametrize("goal, focus", [("lose", "cardio"), ("maintain", "mixed"), ("gain", "strength")])
def test_workout_focus_follows_the_goal(goal, focus):
    assert recommend_workout(goal, 2000, 2000)["focus"] == focus


def test_eating_more_never_makes_the_workout_harder_it_only_adds_a_note():
    over = recommend_workout("lose", 2000, 2000 + SURPLUS_KCAL + 1)
    under = recommend_workout("lose", 2000, 2000 - SURPLUS_KCAL - 1)
    even = recommend_workout("lose", 2000, 2000 + SURPLUS_KCAL)
    assert over["intensity"] == under["intensity"] == even["intensity"] == "moderate"
    assert over["note"] and "don't need to burn it off" in over["note"]
    assert under["note"] and even["note"] is None


def test_the_user_picks_the_intensity_and_harder_means_longer_by_default():
    light, hard = (recommend_workout("lose", 2000, 2000, intensity=i) for i in ("light", "hard"))
    assert light["intensity"] == "light" and hard["intensity"] == "hard"
    assert light["minutes"] < hard["minutes"]


def test_workout_unknown_goal_falls_back_to_mixed():
    assert recommend_workout("bulk", 2000, 2000)["focus"] == "mixed"
