"""
Checks for recommend().
Run:  python -m pytest tests/test_recommend.py
"""
import pytest

from app.recommend import NUTRIENTS, recommend

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
