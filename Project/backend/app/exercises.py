"""
The exercises a workout plan is built from. Plain data, no database: edit this list to add or change
exercises.

Each exercise:
  id         stable slug, used by workout logs and by `avoid`
  name       what the user sees
  kind       "cardio", "strength" or "mobility"
  muscles    from MUSCLES; cardio is "heart"
  equipment  what to look for in the gym ("Bodyweight" needs nothing)
  met        energy cost by intensity, as METs (1 MET = resting). Values are rounded from the
             Compendium of Physical Activities; they are estimates, not measurements.
  dose       per intensity: {"sets", "reps"} for strength (reps may say "30 s"), {"minutes"} for cardio
             and mobility
  how_to     short steps, or None for machines that explain themselves (treadmill, bike, ...)
  tip        one safety or form cue
"""

from urllib.parse import quote_plus

MUSCLES = ["legs", "glutes", "chest", "back", "shoulders", "arms", "core", "heart"]
INTENSITIES = ["light", "moderate", "hard"]

# The same sets and reps for most strength moves: lighter days do fewer sets, harder days more
_SETS_REPS = {"light": {"sets": 2, "reps": "12"}, "moderate": {"sets": 3, "reps": "10"}, "hard": {"sets": 4, "reps": "8"}}
_CORE_HOLD = {"light": {"sets": 2, "reps": "20 s"}, "moderate": {"sets": 3, "reps": "30 s"}, "hard": {"sets": 3, "reps": "45 s"}}
_STRENGTH_MET = {"light": 3.5, "moderate": 5.0, "hard": 6.0}
_STRETCH = {"light": {"minutes": 5}, "moderate": {"minutes": 5}, "hard": {"minutes": 5}}


def _cardio(id, name, equipment, met, how_to=None, tip=None):
    return {"id": id, "name": name, "kind": "cardio", "muscles": ["heart"], "equipment": equipment,
            "met": met, "dose": None, "how_to": how_to, "tip": tip}


def _strength(id, name, muscles, equipment, how_to, tip, dose=None, met=None):
    return {"id": id, "name": name, "kind": "strength", "muscles": muscles, "equipment": equipment,
            "met": met or _STRENGTH_MET, "dose": dose or _SETS_REPS, "how_to": how_to, "tip": tip}


EXERCISES = [
    # ---------- cardio (minutes are set by the plan) ----------
    _cardio("treadmill", "Treadmill walk or run", "Treadmill", {"light": 3.5, "moderate": 6.0, "hard": 9.8},
            tip="Light: brisk walk. Moderate: easy jog or an incline walk. Hard: run or intervals."),
    _cardio("bike", "Stationary bike", "Stationary bike", {"light": 3.5, "moderate": 6.8, "hard": 8.8},
            tip="Set the seat so your knee is only slightly bent at the bottom of the pedal stroke."),
    _cardio("elliptical", "Elliptical", "Elliptical", {"light": 4.0, "moderate": 5.0, "hard": 6.5},
            tip="Stand tall and push through your heels instead of leaning on the handles."),
    _cardio("stair-climber", "Stair climber", "Stair climber", {"light": 4.0, "moderate": 6.5, "hard": 9.0},
            tip="Hold the rails lightly for balance only; leaning on them takes the work away from your legs."),
    _cardio("rower", "Rowing machine", "Rowing machine", {"light": 4.8, "moderate": 7.0, "hard": 8.5},
            how_to=["Strap your feet in and hold the handle with straight arms.",
                    "Push with your legs first, then lean back slightly, then pull the handle to your lower ribs.",
                    "Return in reverse: arms forward, lean forward, then bend your knees.",
                    "Aim for a smooth rhythm, about 2 seconds back and 2 forward."],
            tip="Most of the power comes from the legs; don't yank with your arms or round your back."),
    _cardio("track", "Indoor track walk or jog", "Indoor track", {"light": 3.5, "moderate": 6.0, "hard": 9.0},
            tip="Follow the direction posted for the day and keep to the inside lanes when walking."),
    _cardio("swim", "Lap swimming", "Pool", {"light": 4.8, "moderate": 5.8, "hard": 9.8},
            tip="Pick a lane that matches your speed, and rest at the wall whenever you need to."),
    _cardio("jump-rope", "Jump rope", "Jump rope", {"light": 8.0, "moderate": 10.0, "hard": 12.0},
            how_to=["Hold the handles at hip height with elbows close to your sides.",
                    "Turn the rope with your wrists, not your whole arms.",
                    "Jump just high enough to clear the rope and land softly on the balls of your feet.",
                    "Start with 30 seconds on, 30 seconds rest."],
            tip="Land softly with bent knees; stop if your shins start to ache."),
]
EXERCISES[-1]["max_minutes"] = 10  # jump rope is for short bursts, not a long block
EXERCISES += [

    # ---------- legs and glutes ----------
    _strength("goblet-squat", "Goblet squat", ["legs", "glutes"], "Dumbbells",
              ["Hold one dumbbell upright against your chest, feet a little wider than your hips.",
               "Sit your hips back and down until your thighs are about level with the floor.",
               "Keep your chest up and your knees pointing the same way as your toes.",
               "Push through your whole foot to stand up."],
              "Keep your heels on the floor; if they lift, don't go as low."),
    _strength("back-squat", "Barbell back squat", ["legs", "glutes"], "Squat rack and barbell",
              ["Set the bar at shoulder height in the rack and the safety bars just below your lowest point.",
               "Step under the bar so it rests on your upper back, grip it, and stand up to unrack it.",
               "Take two steps back, then squat down with your chest up until your thighs are about level.",
               "Drive back up, and walk the bar forward into the hooks when you finish."],
              "Always set the safety bars, and start with an empty bar to learn the movement."),
    _strength("leg-press", "Leg press", ["legs", "glutes"], "Leg press machine",
              ["Sit with your back flat on the pad and feet shoulder-width on the platform.",
               "Release the safety handles and lower the platform until your knees are bent about 90 degrees.",
               "Press back up without locking your knees straight.",
               "Lock the safety handles again before getting out."],
              "Keep your lower back on the pad; don't lower the platform so far that it lifts."),
    _strength("rdl", "Romanian deadlift", ["legs", "glutes", "back"], "Dumbbells",
              ["Stand holding a dumbbell in each hand in front of your thighs.",
               "With a slight bend in your knees, push your hips back and slide the weights down your legs.",
               "Stop when you feel a stretch in the back of your thighs, usually around mid-shin.",
               "Squeeze your glutes to stand back up."],
              "Keep your back flat the whole time; the movement comes from the hips, not from bending the spine."),
    _strength("lunges", "Walking lunges", ["legs", "glutes"], "Dumbbells or bodyweight",
              ["Stand tall, holding dumbbells at your sides if you use them.",
               "Take a long step forward and lower until both knees are bent about 90 degrees.",
               "Push off the front foot and bring the back foot forward into the next step.",
               "Count each leg as one rep."],
              "Keep your front knee over your foot, not caving inward."),
    _strength("bodyweight-squat", "Bodyweight squat", ["legs", "glutes"], "Bodyweight",
              ["Stand with feet a little wider than your hips, arms out in front for balance.",
               "Sit your hips back and down as low as you comfortably can, chest up.",
               "Push through your whole foot to stand back up."],
              "Keep your knees pointing the same way as your toes.",
              dose={"light": {"sets": 2, "reps": "15"}, "moderate": {"sets": 3, "reps": "15"}, "hard": {"sets": 4, "reps": "20"}}),
    _strength("step-up", "Step-up", ["legs", "glutes"], "Bench or box",
              ["Stand facing a sturdy bench or box about knee height.",
               "Put one whole foot on it and push through that heel to stand up on top.",
               "Step back down with control, and do all reps on one leg before switching."],
              "Use a surface that won't slide, and push through the top leg instead of jumping off the bottom one."),
    _strength("glute-bridge", "Glute bridge", ["glutes", "core"], "Bodyweight",
              ["Lie on your back with knees bent and feet flat, hip-width apart.",
               "Squeeze your glutes and lift your hips until your body is straight from knees to shoulders.",
               "Pause for a second at the top.",
               "Lower slowly."],
              "Push through your heels and don't arch your lower back at the top."),

    # ---------- chest ----------
    _strength("push-up", "Push-up", ["chest", "arms", "core"], "Bodyweight",
              ["Hands a little wider than your shoulders, body in a straight line from head to heels.",
               "Lower your chest toward the floor, elbows about 45 degrees from your body.",
               "Push back up to straight arms.",
               "Too hard? Do them with your hands on a bench or with your knees down."],
              "Keep your hips in line; don't let them sag or pike up."),
    _strength("db-bench", "Dumbbell bench press", ["chest", "arms", "shoulders"], "Dumbbells and a flat bench",
              ["Lie on the bench holding a dumbbell in each hand at chest level.",
               "Press the weights up until your arms are straight above your chest.",
               "Lower them slowly back to chest level, elbows about 45 degrees from your body.",
               "Keep your feet flat on the floor."],
              "Pick a weight you can control on the way down; ask someone to spot you on heavy sets."),
    _strength("chest-press", "Chest press machine", ["chest", "arms"], "Chest press machine",
              ["Adjust the seat so the handles are at mid-chest height.",
               "Sit with your back against the pad and grip the handles.",
               "Push forward until your arms are almost straight.",
               "Return slowly until you feel a stretch in your chest."],
              "Don't let the weight stack slam down between reps."),

    # ---------- back ----------
    _strength("lat-pulldown", "Lat pulldown", ["back", "arms"], "Lat pulldown machine",
              ["Set the knee pad so your legs are held firmly, then grab the bar a little wider than your shoulders.",
               "Lean back slightly and pull the bar to your upper chest.",
               "Squeeze your shoulder blades down and together at the bottom.",
               "Let the bar rise slowly until your arms are straight."],
              "Pull with your back, not by swinging your body; never pull the bar behind your neck."),
    _strength("cable-row", "Seated cable row", ["back", "arms"], "Cable row machine",
              ["Sit with feet on the platform and knees slightly bent, holding the handle with straight arms.",
               "Sit tall, then pull the handle to your stomach.",
               "Squeeze your shoulder blades together.",
               "Straighten your arms slowly without rounding forward."],
              "Keep your torso still; don't rock back and forth to move the weight."),
    _strength("db-row", "One-arm dumbbell row", ["back", "arms"], "Dumbbell and a flat bench",
              ["Put one knee and one hand on a bench, back flat, and hold a dumbbell in the other hand.",
               "Pull the dumbbell up toward your hip, elbow close to your body.",
               "Lower it slowly until your arm is straight.",
               "Do all reps on one side, then switch."],
              "Keep your back flat and your hips square to the bench."),

    # ---------- shoulders and arms ----------
    _strength("shoulder-press", "Dumbbell shoulder press", ["shoulders", "arms"], "Dumbbells",
              ["Sit or stand holding dumbbells at shoulder height, palms facing forward.",
               "Press them straight up until your arms are straight overhead.",
               "Lower them slowly back to shoulder height."],
              "Brace your stomach so your lower back doesn't arch."),
    _strength("lateral-raise", "Lateral raise", ["shoulders"], "Dumbbells",
              ["Stand holding light dumbbells at your sides.",
               "With a slight bend in your elbows, raise your arms out to the sides up to shoulder height.",
               "Lower them slowly."],
              "Use light weights; swinging means it is too heavy.",
              dose={"light": {"sets": 2, "reps": "12"}, "moderate": {"sets": 3, "reps": "12"}, "hard": {"sets": 3, "reps": "15"}}),
    _strength("biceps-curl", "Dumbbell biceps curl", ["arms"], "Dumbbells",
              ["Stand holding dumbbells at your sides, palms facing forward.",
               "Keeping your elbows by your sides, curl the weights up toward your shoulders.",
               "Lower them slowly."],
              "Keep your upper arms still; don't swing your body to lift the weight."),
    _strength("triceps-pushdown", "Triceps pushdown", ["arms"], "Cable machine",
              ["Attach a rope or bar to the high pulley of a cable machine.",
               "Hold it with elbows tucked at your sides, forearms about level with the floor.",
               "Push down until your arms are straight.",
               "Let it come back up slowly to the starting point."],
              "Only your forearms move; keep your elbows pinned to your sides."),

    # ---------- core ----------
    _strength("plank", "Plank", ["core"], "Bodyweight",
              ["Rest on your forearms and toes, elbows under your shoulders.",
               "Keep your body in a straight line from head to heels.",
               "Squeeze your stomach and glutes and breathe steadily for the whole hold."],
              "Stop the set when your hips start to sag.", dose=_CORE_HOLD, met={"light": 3.0, "moderate": 3.8, "hard": 4.5}),
    _strength("dead-bug", "Dead bug", ["core"], "Bodyweight",
              ["Lie on your back with arms pointing at the ceiling and knees bent at 90 degrees above your hips.",
               "Press your lower back into the floor.",
               "Slowly lower one arm behind your head and the opposite leg toward the floor.",
               "Return and switch sides; each side is one rep."],
              "If your lower back lifts off the floor, don't lower your arm and leg as far.",
              met={"light": 3.0, "moderate": 3.8, "hard": 4.5}),
    _strength("knee-raise", "Hanging knee raise", ["core"], "Pull-up bar or captain's chair",
              ["Hang from a pull-up bar, or rest your forearms on a captain's chair.",
               "Bring your knees up toward your chest without swinging.",
               "Lower them slowly."],
              "Move slowly; if you start swinging, pause until you are still.",
              met={"light": 3.0, "moderate": 3.8, "hard": 4.5}),

    # ---------- mobility (cool-down) ----------
    {"id": "stretch", "name": "Full-body stretch", "kind": "mobility", "muscles": ["legs", "back", "shoulders"],
     "equipment": "Mat", "met": {"light": 2.3, "moderate": 2.3, "hard": 2.3}, "dose": _STRETCH,
     "how_to": ["Hold each stretch about 30 seconds without bouncing: hamstrings, hip flexors, quads, chest, shoulders.",
                "Breathe slowly and relax into each stretch."],
     "tip": "Stretch to mild tension, never to pain."},
]

# The movement each strength move trains, so a plan doesn't stack three kinds of squat. Pulling down
# and rowing are different movements, like pressing overhead and pushing forward, so a back session
# can have a pulldown and a row.
PATTERNS = {
    "goblet-squat": "squat", "back-squat": "squat", "leg-press": "squat", "bodyweight-squat": "squat",
    "lunges": "lunge", "step-up": "lunge", "rdl": "hinge", "glute-bridge": "hinge",
    "push-up": "push", "db-bench": "push", "chest-press": "push",
    "lat-pulldown": "pulldown", "cable-row": "row", "db-row": "row",
    "shoulder-press": "press", "lateral-raise": "raise", "biceps-curl": "curl", "triceps-pushdown": "extension",
    "plank": "hold", "dead-bug": "hold", "knee-raise": "crunch",
}
for _e in EXERCISES:
    _e["pattern"] = PATTERNS.get(_e["id"], _e["id"])  # cardio and stretches are their own pattern

BY_ID = {e["id"]: e for e in EXERCISES}


def video_url(exercise: dict) -> str | None:
    """A YouTube search for the exercise's form, or None for self-explanatory machines. A search link
    never goes stale the way a single video can."""
    if not exercise.get("how_to"):
        return None
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"how to do {exercise['name']} proper form")


def kcal_burned(met: float, weight_lbs: float, minutes: float) -> float:
    """Standard estimate: kcal = MET x body weight (kg) x hours."""
    return met * (weight_lbs / 2.20462) * minutes / 60
