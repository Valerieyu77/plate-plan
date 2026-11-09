"""
Building a workout from the exercise list in exercises.py. Plain functions, no database access.

A plan is a warm-up, a main block and a cool-down:
  cardio    one cardio machine for most of the time, plus a core move when there is room
  strength  one move per muscle group, going round the groups until the time is used
  mixed     half cardio, half strength
The user may pick the muscle groups, the length, the intensity and whether they have equipment;
everything else has a default. Which move is picked for a group rotates by `seed` (the date, so the
same day gives the same plan), and `avoid` steers away from moves already shown ("show me another").
"""

import random

from .exercises import BY_ID, EXERCISES, INTENSITIES, MUSCLES, kcal_burned, video_url

FOCUSES = ["cardio", "strength", "mixed"]
DEFAULT_GROUPS = ["legs", "chest", "back", "shoulders", "core"]  # a full-body session
MIN_MINUTES, MAX_MINUTES = 10, 120
WARM_UP = 5   # minutes of easy cardio before strength work
COOL_DOWN = 5  # minutes of stretching, when the session is long enough for it
COOL_DOWN_FROM = 25
MINUTES_PER_SET = 1.5  # one set plus the rest after it
CORE_MINUTES = 5
MAX_STRENGTH_MOVES = 8  # more than this in one session is too many different things to learn
MAX_PER_GROUP = 3       # moves for any one muscle group; past that, the plan adds sets instead
FINISHER_MAX = 15       # most minutes of cardio added to fill a strength session
MAX_SETS = 5            # a long session adds sets to its moves, up to this many
WARM_UP_MACHINES = ["treadmill", "bike", "elliptical", "rower", "track"]
FINISHER_MACHINES = WARM_UP_MACHINES + ["stair-climber"]
NO_EQUIPMENT = {"Bodyweight", "Dumbbells or bodyweight", "Indoor track", "Mat"}


def _usable(exercise: dict, no_equipment: bool) -> bool:
    return not no_equipment or exercise["equipment"] in NO_EQUIPMENT


def _line(exercise: dict, intensity: str, weight_lbs: float | None, minutes: float | None = None) -> dict:
    """One exercise in the plan: what to do, for how long, and roughly what it burns."""
    dose = (exercise["dose"] or {}).get(intensity, {})
    if exercise["kind"] == "strength":
        minutes = dose["sets"] * MINUTES_PER_SET
    elif minutes is None:
        minutes = dose.get("minutes", COOL_DOWN)
    met = exercise["met"][intensity]
    return {
        "id": exercise["id"],
        "name": exercise["name"],
        "kind": exercise["kind"],
        "muscles": exercise["muscles"],
        "equipment": exercise["equipment"],
        "sets": dose.get("sets"),
        "reps": dose.get("reps"),
        "minutes": round(minutes, 1),
        "kcal": round(kcal_burned(met, weight_lbs, minutes)) if weight_lbs else None,
        "how_to": exercise["how_to"],
        "tip": exercise["tip"],
        "video_url": video_url(exercise),
    }


def _pick(tiers: list[list[dict]], rng: random.Random, avoid: set, taken: set) -> dict | None:
    """A random move not already in the plan, from the first tier that has one, preferring moves
    the user hasn't been shown."""
    for candidates in tiers:
        fresh = [e for e in candidates if e["id"] not in taken]
        if fresh:
            preferred = [e for e in fresh if e["id"] not in avoid] or fresh
            return rng.choice(preferred)
    return None


def _cardio_choices(no_equipment: bool, minutes: float, ids: list[str] | None = None) -> list[list[dict]]:
    pool = [BY_ID[i] for i in ids] if ids else [e for e in EXERCISES if e["kind"] == "cardio"]
    return [[e for e in pool if _usable(e, no_equipment) and e.get("max_minutes", MAX_MINUTES) >= minutes]]


def _strength_for(group: str, no_equipment: bool, used_patterns=frozenset(), repeats: bool = True) -> list[list[dict]]:
    """Strength moves for a muscle group, best first: moves that mainly train it with a movement not
    yet in the plan (a lunge after a squat, not a second squat), then moves that also work it with a
    new movement (a push-up counts for arms once the curls are used), then, if `repeats`, the rest."""
    moves = [e for e in EXERCISES if e["kind"] == "strength" and group in e["muscles"] and _usable(e, no_equipment)]
    main = [e for e in moves if e["muscles"][0] == group]
    new = lambda pool: [e for e in pool if e["pattern"] not in used_patterns]
    return [new(main), new(moves)] + ([main, moves] if repeats else [])


def build_plan(focus: str, intensity: str = "moderate", minutes: int | None = None, weight_lbs: float | None = None,
               muscles: list[str] | None = None, no_equipment: bool = False, avoid=(), seed: str = "") -> dict:
    """
    {"focus", "intensity", "minutes", "exercises": [line, ...], "total_kcal"}; see _line() for a line.
    Raises ValueError for an unknown focus, intensity or muscle group, or a length out of range.
    """
    if focus not in FOCUSES:
        raise ValueError(f"focus must be one of {FOCUSES}")
    if intensity not in INTENSITIES:
        raise ValueError(f"intensity must be one of {INTENSITIES}")
    unknown = sorted(set(muscles or []) - set(MUSCLES))
    if unknown:
        raise ValueError(f"unknown muscle group(s) {unknown}; choose from {MUSCLES}")
    minutes = minutes or 35
    if not MIN_MINUTES <= minutes <= MAX_MINUTES:
        raise ValueError(f"minutes must be between {MIN_MINUTES} and {MAX_MINUTES}")

    rng = random.Random(f"{seed}|{focus}|{intensity}|{minutes}|{','.join(sorted(muscles or []))}")
    avoid, taken, lines = set(avoid), set(), []

    def add(exercise, minutes=None, level=intensity):
        taken.add(exercise["id"])
        lines.append(_line(exercise, level, weight_lbs, minutes))

    cool_down = COOL_DOWN if minutes >= COOL_DOWN_FROM else 0
    groups = [m for m in (muscles or DEFAULT_GROUPS) if m != "heart"] or DEFAULT_GROUPS
    main = minutes - cool_down

    if focus in ("strength", "mixed"):
        warm = _pick(_cardio_choices(no_equipment, WARM_UP, WARM_UP_MACHINES), rng, avoid, taken)
        if warm:
            add(warm, WARM_UP, "light")
            main -= WARM_UP

    cardio_minutes = main if focus == "cardio" else (main / 2 if focus == "mixed" else 0)
    if focus == "cardio" and main >= CORE_MINUTES * 4:
        cardio_minutes -= CORE_MINUTES  # leave room for one core move
    if cardio_minutes:
        machine = _pick(_cardio_choices(no_equipment, cardio_minutes), rng, avoid, taken)
        if machine:
            add(machine, cardio_minutes)

    if focus == "cardio":
        if main >= CORE_MINUTES * 4:
            core = _pick(_strength_for("core", no_equipment), rng, avoid, taken)
            if core:
                add(core)
    else:
        # Go round the muscle groups, one move each, until the strength time is used up
        budget = main - cardio_minutes
        per_move = BY_ID["goblet-squat"]["dose"][intensity]["sets"] * MINUTES_PER_SET
        moves, per_group, patterns = 0, dict.fromkeys(groups, 0), set()
        while budget >= per_move * 0.75 and moves < MAX_STRENGTH_MOVES:
            added = False
            for group in groups:
                if budget < per_move * 0.75 or moves >= MAX_STRENGTH_MOVES:
                    break
                if per_group[group] >= MAX_PER_GROUP:
                    continue
                # A second squat only if the plan would otherwise be too thin; else more sets instead
                move = _pick(_strength_for(group, no_equipment, patterns, repeats=moves < 2), rng, avoid, taken)
                if move:
                    add(move)
                    patterns.add(move["pattern"])
                    budget -= lines[-1]["minutes"]
                    moves += 1
                    per_group[group] += 1
                    added = True
            if not added:
                break
        # Still time left (a long session, or few moves for these groups): add sets to the moves
        # already in the plan, up to MAX_SETS each, before reaching for cardio
        strength = [line for line in lines if line["kind"] == "strength"]
        while strength and budget >= MINUTES_PER_SET and any(line["sets"] < MAX_SETS for line in strength):
            for line in strength:
                if budget < MINUTES_PER_SET or line["sets"] >= MAX_SETS:
                    continue
                line["sets"] += 1
                line["minutes"] = round(line["minutes"] + MINUTES_PER_SET, 1)
                if weight_lbs:
                    line["kcal"] = round(kcal_burned(BY_ID[line["id"]]["met"][intensity], weight_lbs, line["minutes"]))
                budget -= MINUTES_PER_SET
        # Time left over (few moves for these groups, or a long session): finish with some cardio
        if budget >= WARM_UP:
            finish = min(budget, FINISHER_MAX)
            # A gym machine, not the pool: nobody changes into swimwear for the last 10 minutes
            finisher = _pick(_cardio_choices(no_equipment, finish, FINISHER_MACHINES), rng, avoid, taken)
            if finisher:
                add(finisher, finish)

    if cool_down:
        add(BY_ID["stretch"], cool_down, "light")

    kcal = [line["kcal"] for line in lines]
    return {
        "focus": focus,
        "intensity": intensity,
        "minutes": round(sum(line["minutes"] for line in lines)),
        "exercises": lines,
        "total_kcal": round(sum(kcal)) if weight_lbs else None,
    }
