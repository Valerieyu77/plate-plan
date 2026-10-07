from types import SimpleNamespace as NS

from app.dietary import ALLERGENS, NON_ALLERGEN_TAGS, allowed_for_user, violates_allergies


def item(tags=(), veg=False, vegan=False):
    return NS(allergens=list(tags), is_vegetarian=veg or vegan, is_vegan=vegan)


def user(allergies=(), restrictions=()):
    return NS(allergies=list(allergies), dietary_restrictions=list(restrictions))


def test_allergy_blocks_matching_tag_case_insensitively():
    assert not allowed_for_user(item(["Milk", "Wheat"]), user(allergies=["milk"]))
    assert allowed_for_user(item(["Wheat"]), user(allergies=["Milk"]))


def test_no_restrictions_allows_everything():
    assert allowed_for_user(item(["Milk", "Pork", "Alcohol"]), user())


def test_vegetarian_and_vegan_use_flags_not_tags():
    assert not allowed_for_user(item(["Milk"]), user(restrictions=["Vegetarian"]))
    assert allowed_for_user(item(veg=True), user(restrictions=["vegetarian"]))
    assert not allowed_for_user(item(veg=True), user(restrictions=["vegan"]))
    assert allowed_for_user(item(vegan=True), user(restrictions=["vegan"]))


def test_halal_kosher_require_the_tag():
    assert allowed_for_user(item(["Halal"]), user(restrictions=["halal"]))
    assert not allowed_for_user(item(["Kosher"]), user(restrictions=["halal"]))
    assert not allowed_for_user(item([]), user(restrictions=["kosher"]))


def test_no_pork_blocks_pork_tag():
    assert not allowed_for_user(item(["Pork"]), user(restrictions=["no pork"]))
    assert allowed_for_user(item(["Milk"]), user(restrictions=["no pork"]))


def test_lifestyle_tags_are_not_allergies_by_accident():
    # Kosher on a dish must not hide it from a user who simply isn't allergic to anything
    assert allowed_for_user(item(["Kosher", "Halal", "Jain", "Local"]), user(allergies=["Milk"]))


def test_violates_allergies_handles_none():
    assert not violates_allergies(None, None)
    assert not violates_allergies([], ["Milk"])


def test_name_lists_do_not_overlap():
    assert not {a.lower() for a in ALLERGENS} & {t.lower() for t in NON_ALLERGEN_TAGS}
