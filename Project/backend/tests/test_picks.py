import pytest

from app.picks import high_protein_target, match_score, protein_share

TARGET = {"kcal": 600, "protein_g": 45, "carbs_g": 65, "fat_g": 18}


def test_a_plate_on_target_scores_100():
    assert match_score(TARGET, dict(TARGET)) == 100


def test_the_further_off_the_lower_the_score():
    close = match_score(TARGET, {"kcal": 590, "protein_g": 43, "carbs_g": 66, "fat_g": 19})
    off = match_score(TARGET, {"kcal": 500, "protein_g": 25, "carbs_g": 70, "fat_g": 12})
    assert 90 <= close < 100
    assert off < close - 15


def test_protein_counts_more_than_fat():
    protein_off = match_score(TARGET, {**TARGET, "protein_g": 22.5})  # 50% under on protein
    fat_off = match_score(TARGET, {**TARGET, "fat_g": 9})  # 50% under on fat
    assert protein_off < fat_off


def test_an_empty_plate_scores_zero_and_scores_never_leave_0_to_100():
    assert match_score(TARGET, {}) == 0
    assert match_score(TARGET, {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}) == 0
    assert 0 <= match_score(TARGET, {"kcal": 9000, "protein_g": 900, "carbs_g": 900, "fat_g": 900}) <= 100


def test_high_protein_target_splits_the_calories_40_35_25():
    t = high_protein_target(600)
    assert t["kcal"] == 600
    assert 4 * t["protein_g"] == pytest.approx(0.40 * 600, abs=1)
    assert 4 * t["carbs_g"] == pytest.approx(0.35 * 600, abs=1)
    assert 9 * t["fat_g"] == pytest.approx(0.25 * 600, abs=1)


def test_protein_share_is_the_percent_of_calories_from_protein():
    assert protein_share({"kcal": 600, "protein_g": 60}) == 40
    assert protein_share({"kcal": 0, "protein_g": 0}) == 0
    assert protein_share({}) == 0
