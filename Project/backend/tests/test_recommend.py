"""
Checks for recommend(). They are skipped until you implement it: delete one @skip line at a time.
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
SKIP = "remove this line once recommend() is written"


@pytest.mark.skip(reason=SKIP)
def test_result_has_the_agreed_shape():
    r = recommend(TARGET, MENU)
    assert set(r) >= {"items", "total", "target", "note"}
    assert r["target"] == TARGET
    for line in r["items"]:
        assert set(line) >= {"item_id", "name", "servings", *NUTRIENTS}


@pytest.mark.skip(reason=SKIP)
def test_total_is_the_sum_of_the_lines():
    r = recommend(TARGET, MENU)
    for k in NUTRIENTS:
        assert r["total"][k] == pytest.approx(sum(line[k] for line in r["items"]))


@pytest.mark.skip(reason=SKIP)
def test_gets_close_to_a_reachable_target():
    r = recommend(TARGET, MENU)
    assert abs(r["total"]["kcal"] - TARGET["kcal"]) <= 0.1 * TARGET["kcal"]


@pytest.mark.skip(reason=SKIP)
def test_never_exceeds_max_servings():
    r = recommend(TARGET, MENU, max_servings=2)
    assert all(line["servings"] <= 2 for line in r["items"])


@pytest.mark.skip(reason=SKIP)
def test_unreachable_target_returns_closest_with_a_note():
    r = recommend({"kcal": 5000, "protein_g": 300, "carbs_g": 500, "fat_g": 100}, MENU[:1], max_servings=1)
    assert r["items"] and r["note"]
