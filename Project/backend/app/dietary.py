"""
Shared rules for matching a user's allergies / dietary restrictions against menu items.

The dining site puts everything into one tag list. MenuItem.allergens therefore mixes real
allergens (Milk, Peanuts, ...) with lifestyle/religious labels (Kosher, Halal, Pork, ...).
This module is the single place that says which is which.

Use the canonical names below for User.allergies and User.dietary_restrictions (matching is
case-insensitive).

    allowed_for_user(item, user)   -> True if the dish is OK for this user
"""

from typing import Iterable

# Tags that can make someone ill. A user listing any of these in `allergies` must not get
# a dish carrying that tag. Any tag NOT listed in NON_ALLERGEN_TAGS is also treated as an
# allergen, so a brand-new tag from the site fails safe (hidden) instead of slipping through.
ALLERGENS = [
    "Milk", "Eggs", "Fish", "Shellfish", "Peanuts", "Tree Nuts", "Soy", "Wheat", "Gluten",
    "Sesame", "Corn", "Coconut", "Sulfites", "MSG", "Red Dye",
]

# Tags that describe how a dish is made, not an allergen. Used for dietary_restrictions.
NON_ALLERGEN_TAGS = ["Kosher", "Halal", "Jain", "Local", "Pork", "Alcohol", "Gelatin", "Sustainable Seafood"]

# dietary_restrictions value -> (what the dish must have, what it must NOT have)
# "vegetarian"/"vegan" use MenuItem.is_vegetarian / is_vegan; the rest use tags.
_MUST_HAVE_TAG = {"kosher": "Kosher", "halal": "Halal", "jain": "Jain"}
_MUST_NOT_HAVE_TAG = {
    "no pork": "Pork", "no alcohol": "Alcohol", "no gelatin": "Gelatin",
}

SUPPORTED_RESTRICTIONS = ["vegetarian", "vegan", *_MUST_HAVE_TAG, *_MUST_NOT_HAVE_TAG]


def _norm(values: Iterable[str] | None) -> set[str]:
    return {v.strip().lower() for v in (values or []) if v and v.strip()}


def violates_allergies(item_tags: Iterable[str] | None, user_allergies: Iterable[str] | None) -> bool:
    """True if the dish carries any tag the user is allergic to."""
    return bool(_norm(item_tags) & _norm(user_allergies))


def allowed_for_user(item, user) -> bool:
    """
    item: a MenuItem (needs .allergens, .is_vegetarian, .is_vegan)
    user: a User (uses .allergies and .dietary_restrictions)
    Unknown restriction strings are ignored, never silently treated as satisfied: they are
    listed in SUPPORTED_RESTRICTIONS so callers can validate input.
    """
    tags = _norm(item.allergens)
    if violates_allergies(item.allergens, user.allergies):
        return False
    for restriction in _norm(user.dietary_restrictions):
        if restriction == "vegetarian" and not item.is_vegetarian:
            return False
        if restriction == "vegan" and not item.is_vegan:
            return False
        if restriction in _MUST_HAVE_TAG and _MUST_HAVE_TAG[restriction].lower() not in tags:
            return False
        if restriction in _MUST_NOT_HAVE_TAG and _MUST_NOT_HAVE_TAG[restriction].lower() in tags:
            return False
    return True
