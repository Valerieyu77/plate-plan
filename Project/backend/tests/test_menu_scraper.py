from pathlib import Path

import pytest

from scraper.menu_scraper import (
    is_complete,
    parse_nutrition_label,
    parse_number,
    parse_serving,
    split_tags,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("text, expected", [
    ("8g", 8.0),
    ("160mg", 160.0),
    ("1.5g", 1.5),
    ("0g", 0.0),
    ("NA", None),
    ("", None),
    (None, None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("raw, size, unit, grams", [
    ("Each (38g)", 1.0, "Each", 38.0),
    ("Each\xa0(38g)", 1.0, "Each", 38.0),
    ("Slice (1/96) (44g)", 1.0, "Slice (1/96)", 44.0),
    ("4 oz (113g)", 4.0, "oz", 113.0),
    ("1/2 Cup (120g)", 1.0, "1/2 Cup", 120.0),
    ("Cup", 1.0, "Cup", None),
    (None, None, None, None),
])
def test_parse_serving(raw, size, unit, grams):
    assert parse_serving(raw) == {
        "serving_size": size, "serving_unit": unit, "serving_grams": grams,
    }


def test_parse_nutrition_label_real_page():
    label = parse_nutrition_label((FIXTURES / "sugar_cookies_label.html").read_text())
    assert label["name"] == "Sugar Cookies"
    assert label["kcal"] == 170.0
    assert label["protein_g"] == 2.0
    assert label["carbs_g"] == 22.0
    assert label["fat_g"] == 8.0
    assert label["saturated_fat_g"] == 1.5
    assert label["fiber_g"] == 0.0
    assert label["sodium_mg"] == 160.0
    assert label["sugar_g"] is None  # the site shows "NA"
    assert label["serving_unit"] == "Each"
    assert label["serving_grams"] == 38.0
    assert label["ingredients"].startswith("ENRICHED FLOUR")
    assert "Contains:" not in label["ingredients"]


def test_parse_nutrition_label_macros_agree_with_calories():
    label = parse_nutrition_label((FIXTURES / "sugar_cookies_label.html").read_text())
    estimate = 4 * label["protein_g"] + 4 * label["carbs_g"] + 9 * label["fat_g"]
    assert abs(estimate - label["kcal"]) < 0.2 * label["kcal"]


def test_parse_nutrition_label_empty_page_is_incomplete():
    label = parse_nutrition_label("<div id='nutritionLabel'></div>")
    assert not is_complete(label)


def test_split_tags_separates_diet_flags_from_allergens():
    out = split_tags(["Eggs", "Milk", "Vegetarian"])
    assert out == {"allergens": ["Eggs", "Milk"], "is_vegetarian": True, "is_vegan": False}


def test_split_tags_vegan_implies_vegetarian():
    out = split_tags(["Soy", "Vegan"])
    assert out["is_vegan"] and out["is_vegetarian"]
    assert out["allergens"] == ["Soy"]


def test_split_tags_empty():
    assert split_tags([]) == {"allergens": [], "is_vegetarian": False, "is_vegan": False}


def test_is_complete_requires_kcal_and_all_macros():
    full = {"kcal": 100, "protein_g": 1, "carbs_g": 2, "fat_g": 3}
    assert is_complete(full)
    assert is_complete({**full, "protein_g": 0})  # zero is a real value
    for key in full:
        assert not is_complete({**full, key: None})
