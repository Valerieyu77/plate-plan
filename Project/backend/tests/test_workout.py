import pytest

from app.exercises import BY_ID, EXERCISES, MUSCLES, kcal_burned, video_url
from app.workout import FINISHER_MAX, MAX_STRENGTH_MOVES, NO_EQUIPMENT, build_plan


def test_every_exercise_is_complete():
    ids = [e["id"] for e in EXERCISES]
    assert len(ids) == len(set(ids))
    for e in EXERCISES:
        assert e["kind"] in ("cardio", "strength", "mobility")
        assert e["muscles"] and set(e["muscles"]) <= set(MUSCLES)
        assert e["equipment"] and e["tip"]
        assert set(e["met"]) == {"light", "moderate", "hard"} and all(v > 1 for v in e["met"].values())
        if e["kind"] == "strength":
            assert e["how_to"], e["id"]  # every strength move explains itself
            assert all({"sets", "reps"} <= set(d) for d in e["dose"].values())


def test_machines_that_explain_themselves_have_no_video_and_the_rest_link_a_search():
    assert video_url(BY_ID["treadmill"]) is None and video_url(BY_ID["elliptical"]) is None
    url = video_url(BY_ID["goblet-squat"])
    assert url.startswith("https://www.youtube.com/results?search_query=") and "Goblet+squat" in url


def test_kcal_estimate_uses_met_weight_and_time():
    # 8 METs for 30 minutes at 60 kg (132.3 lb) is 240 kcal
    assert kcal_burned(8, 60 * 2.20462, 30) == pytest.approx(240)


@pytest.mark.parametrize("focus", ["cardio", "strength", "mixed"])
@pytest.mark.parametrize("minutes", [10, 20, 35, 60, 120])
def test_a_plan_roughly_fills_the_time_asked(focus, minutes):
    plan = build_plan(focus, "moderate", minutes, 150, seed="x")
    assert plan["exercises"]
    assert 0.6 * minutes <= plan["minutes"] <= minutes + 1
    assert plan["total_kcal"] == pytest.approx(sum(l["kcal"] for l in plan["exercises"]), abs=len(plan["exercises"]))


def test_no_move_appears_twice_and_strength_sessions_stay_learnable():
    for focus in ("strength", "mixed"):
        for minutes in (35, 120):
            plan = build_plan(focus, "light", minutes, 150, seed="y")
            ids = [l["id"] for l in plan["exercises"]]
            assert len(ids) == len(set(ids))
            assert sum(l["kind"] == "strength" for l in plan["exercises"]) <= MAX_STRENGTH_MOVES


def test_strength_covers_the_whole_body_by_default():
    plan = build_plan("strength", "moderate", 40, 150, seed="z")
    worked = {m for l in plan["exercises"] if l["kind"] == "strength" for m in l["muscles"]}
    assert {"legs", "chest", "back", "shoulders", "core"} <= worked
    assert plan["exercises"][0]["kind"] == "cardio" and plan["exercises"][0]["minutes"] == 5  # warm-up
    assert plan["exercises"][-1]["id"] == "stretch"  # cool-down


def test_the_user_picks_the_muscles():
    plan = build_plan("strength", "moderate", 30, 150, muscles=["arms"], seed="a")
    strength = [l for l in plan["exercises"] if l["kind"] == "strength"]
    assert strength and all("arms" in l["muscles"] for l in strength)


def test_no_equipment_means_bodyweight_only():
    for focus in ("cardio", "strength", "mixed"):
        plan = build_plan(focus, "moderate", 45, 150, no_equipment=True, seed="b")
        assert all(l["equipment"] in NO_EQUIPMENT for l in plan["exercises"]), focus


def test_few_moves_for_a_group_are_topped_up_with_a_short_cardio_finisher():
    plan = build_plan("strength", "moderate", 60, 150, muscles=["arms"], seed="c")
    cardio = [l for l in plan["exercises"] if l["kind"] == "cardio"]
    assert all(l["minutes"] <= FINISHER_MAX for l in cardio[1:])
    assert all(l["id"] != "jump-rope" or l["minutes"] <= 10 for l in plan["exercises"])


def test_same_seed_same_plan_and_avoid_gives_something_else():
    a = build_plan("strength", "moderate", 35, 150, seed="2026-10-28")
    assert a == build_plan("strength", "moderate", 35, 150, seed="2026-10-28")
    shown = [l["id"] for l in a["exercises"] if l["kind"] == "strength"]
    b = build_plan("strength", "moderate", 35, 150, avoid=shown, seed="2026-10-28")
    new = [l["id"] for l in b["exercises"] if l["kind"] == "strength"]
    assert len(set(new) - set(shown)) >= len(new) - 1


def test_harder_means_more_sets_and_more_kcal_per_minute():
    light = build_plan("strength", "light", 40, 150, seed="d")
    hard = build_plan("strength", "hard", 40, 150, seed="d")
    sets = lambda p: max(l["sets"] or 0 for l in p["exercises"])
    assert sets(light) < sets(hard)
    assert light["total_kcal"] / light["minutes"] < hard["total_kcal"] / hard["minutes"]


def test_without_a_weight_there_is_no_kcal_estimate():
    plan = build_plan("cardio", "moderate", 30, None)
    assert plan["total_kcal"] is None and all(l["kcal"] is None for l in plan["exercises"])


@pytest.mark.parametrize("kwargs", [
    {"focus": "yoga"}, {"intensity": "extreme"}, {"minutes": 5}, {"minutes": 500}, {"muscles": ["toes"]},
])
def test_bad_choices_are_refused(kwargs):
    args = {"focus": "mixed", "intensity": "moderate", "minutes": 30, **kwargs}
    with pytest.raises(ValueError):
        build_plan(args.pop("focus"), **args)


@pytest.mark.parametrize("muscles, minutes", [(["legs"], 35), (["legs", "glutes"], 45), (["arms"], 60), (["back"], 30)])
def test_one_group_gets_different_movements_not_three_kinds_of_squat(muscles, minutes):
    from app.workout import MAX_PER_GROUP

    plan = build_plan("strength", "moderate", minutes, 150, muscles=muscles, seed="2026-11-08")
    strength = [BY_ID[l["id"]] for l in plan["exercises"] if l["kind"] == "strength"]
    patterns = [e["pattern"] for e in strength]
    assert len(patterns) == len(set(patterns)), patterns
    assert len(strength) <= MAX_PER_GROUP * len(muscles)
    assert plan["minutes"] >= 0.7 * minutes  # the time goes into extra sets or a short finisher instead


def test_a_back_session_has_a_pulldown_and_a_row():
    for seed in range(20):
        plan = build_plan("strength", "moderate", 45, 150, muscles=["back"], seed=str(seed))
        ids = {l["id"] for l in plan["exercises"]}
        assert "lat-pulldown" in ids and ids & {"cable-row", "db-row"}, ids


def test_a_strength_finisher_is_a_gym_machine_not_the_pool():
    for seed in range(20):
        plan = build_plan("strength", "moderate", 60, 150, muscles=["arms"], seed=str(seed))
        assert all(l["id"] != "swim" for l in plan["exercises"])
