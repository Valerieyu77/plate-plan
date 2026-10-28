# API specification (prototype)

Draft for the whole team to confirm. Frontend can build against this with mock data now; backend
switches mock to real without changing the shapes. If you need a change, post it in the group chat
first and update this file in the same PR.

Base URL: `http://127.0.0.1:8000` locally. Interactive docs: `/docs`.

## Conventions
- JSON everywhere. Dates are ISO strings: `"2026-10-08"`.
- Units: weight in **lbs**, height in **inches**, nutrients in **g** (sodium in mg), energy in **kcal**.
- All nutrient values on a menu item are **per ONE serving**.
- Login: `POST /auth/signup` and `POST /auth/login` return `{token, user}`. Send the token on every request as `Authorization: Bearer <token>`. Every `/users/{id}/...` endpoint, and `user_id=` on `/menu-items` and `/recommendations/meals`, only accepts that user's own token. Tokens last 30 days.
- Errors: `401` not logged in / bad token / wrong password, `403` someone else's `user_id`, `404` not found, `409` duplicate email, `422` invalid input. Body: `{"detail": "..."}`.
- The server needs `JWT_SECRET` (a long random string) in `Project/backend/.env` and on Render. Without it, every restart logs everyone out.
- CORS is enabled for `http://localhost:5173`, `http://localhost:3000` and any `https://*.vercel.app` (PR #9). Tell C if the frontend runs somewhere else.

Status: ✅ built and merged, 🟡 build with mock data first, ⬜ not started.

## User flow → endpoints

| Step in the app | Endpoint |
|---|---|
| Sign up with body info / log in | `POST /auth/signup` ✅, `POST /auth/login` ✅, `GET /auth/me` ✅ |
| Set a goal (steady pace or target weight + date), get daily targets | `POST /users/{id}/goal/preview` ✅, `PUT /users/{id}/goal` ✅ |
| Pick a meal first, then a hall that serves it | `GET /halls?meal=` ✅, `GET /meal-options` ✅ |
| See this meal's target and the dishes the user can eat | `GET /users/{id}/meal-target` ✅, `GET /menu-items?user_id=` ✅ |
| Get recommended dishes for that meal | `GET /recommendations/meals` 🟡 (D) |
| Check off / un-check what was eaten | `POST` ✅ and `DELETE /users/{id}/food-logs` ✅ |
| Log weight | `POST /users/{id}/weight-logs` ✅ |
| Progress page: target vs actual, weight trend, plan vs actual weight | `GET /users/{id}/progress` ✅, `GET /users/{id}/goal/timeline` ✅ |
| Get a workout (pick muscles, length, intensity, or nothing at all) | `GET /users/{id}/workout` ✅, `GET /exercises` ✅ |
| Log a workout (optional) | `POST`, `GET`, `DELETE /users/{id}/workout-logs` ✅ |
| Calories in vs out today; ahead or behind the plan, finishing early or late | `GET /users/{id}/energy` ✅, `GET /users/{id}/goal/progress` ✅ |
| Campus fitness events | `GET /events` ✅ |

Everything marked ✅ is in PR #9 (or already merged) and has tests.

## Endpoints

### `POST /auth/signup` ✅
Create an account. Returns `201` with `{"token": "...", "user": {...}}` (the user includes `id`), `409` if the email exists (any letter case). Emails are stored lowercase. Passwords are 8–72 bytes and only a bcrypt hash is kept.
```json
{
  "name": "Val", "email": "val@example.com", "password": "correct horse",
  "weight_lbs": 140, "height_in": 64, "gender": "female",
  "birthdate": "2004-05-17", "activity_level": "moderate",
  "allergies": ["Milk", "Peanuts"],
  "dietary_restrictions": ["vegetarian"]
}
```
- `allergies` names: Milk, Eggs, Fish, Shellfish, Peanuts, Tree Nuts, Soy, Wheat, Gluten, Sesame, Corn, Coconut, Sulfites, MSG, Red Dye.
- `dietary_restrictions`: vegetarian, vegan, kosher, halal, jain, no pork, no alcohol, no gelatin. (See `app/dietary.py`.)
- `activity_level` (optional, default `light`): one of `sedentary`, `light`, `moderate`, `active`, `very_active`. Anything else gets `422`.

### `POST /auth/login` ✅
`{"email": "...", "password": "..."}` → `{"token": "...", "user": {...}}`. Returns `401 "Incorrect email or password"` for a wrong password or an unknown email alike. Accounts made before login existed have no password and can't log in; sign up again.

### `GET /auth/me` ✅
The user the token belongs to. The frontend calls it on page load to restore the session.

### `GET /users/{id}` ✅
Returns the same shape as above plus `id`.

### `PUT /users/{id}/goal` ✅
Set the goal; the daily targets are calculated and saved. Send **either** a goal type (steady pace, no end date) **or** a timeline:
```json
// steady pace: lose (-450 kcal), maintain (0) or gain (+400 kcal)
{ "goal_type": "lose" }
// timeline: the pace sets the calories; goal_type follows from the target
{ "target_weight_lbs": 130, "target_date": "2026-12-20" }
// response
{
  "user_id": 1, "goal_type": "lose", "target_weight_lbs": 130, "target_date": "2026-12-20",
  "start_date": "2026-10-27", "start_weight_lbs": 140, "weekly_rate_lbs": 1.3,
  "calorie_goal": 1500, "protein_goal_g": 127, "carb_goal_g": 160, "fat_goal_g": 42, "sugar_limit_g": null,
  "tier": "aggressive", "warning": "1.3 lb a week is on the fast side. ..."
}
```
- `422` if the profile lacks weight, height, gender or birthdate (the message lists what is missing), for a date in the past or more than 2 years away, and for an **unsafe** timeline (the message says why; use the preview below to offer alternatives). Nothing is saved then.
- `tier` (timeline only): `healthy` or `aggressive`. `warning` is set if the calories were raised to the safe minimum or the pace is aggressive.
- A steady-pace goal clears any timeline.
- Each weigh-in (`POST /users/{id}/weight-logs`) recalculates a timeline goal's calories from what is left and the days left, never faster than the safe maximum. Once the target is reached or the date passes, the targets switch to maintaining.

Safety rules (`app/timeline.py`, about 3,500 kcal per lb):

| | Healthy | Aggressive (saved, with a warning) | Unsafe (refused) |
|---|---|---|---|
| Loss | ≤ 1 lb/week | ≤ 2 lb/week and ≤ 1% of body weight/week | faster, or under the calorie minimum (1200 F / 1500 M) |
| Gain | ≤ 0.5 lb/week | ≤ 1 lb/week | faster |
| Also unsafe | | | under 7 days to the date; a target BMI under 18.5 |

### `POST /users/{id}/goal/preview` ✅
Same timeline body as above; checks it without saving. Always `200` for a valid request:
```json
{
  "goal_type": "lose", "start_weight_lbs": 140, "target_weight_lbs": 120, "target_date": "2026-10-29", "days": 2,
  "weekly_rate_lbs": 70.0, "daily_calorie_change": -35000,
  "calorie_goal": 1200, "protein_goal_g": 127, "carb_goal_g": 71, "fat_goal_g": 33, "warning": "...",
  "tier": "unsafe",
  "issues": ["Give yourself at least 7 days; ..."],
  "alternatives": {
    "target_weight_lbs": 120,               // moved up to a healthy weight if the target was underweight
    "earliest_date": "2027-02-04",          // same target at the fastest safe pace
    "recommended_date": "2027-03-16",       // same target at a healthy pace
    "target_weight_by_date": null           // most that can safely change by the chosen date (null under 7 days)
  }
}
```
`alternatives` is `null` for maintaining. `issues` is empty unless `tier` is `unsafe`.

### `GET /users/{id}/goal` ✅
Returns the stored goal (same fields as the `PUT` response, without `tier`/`warning`). `404` if none.

### `GET /users/{id}/goal/timeline` ✅
Planned vs actual weight for the progress chart. `404` if the goal has no timeline.
```json
{
  "goal_type": "lose", "start_date": "2026-10-27", "start_weight_lbs": 140,
  "target_date": "2026-12-22", "target_weight_lbs": 132, "weekly_rate_lbs": 1.0,
  "planned": [ { "date": "2026-10-27", "weight_lbs": 140 }, { "date": "2026-11-03", "weight_lbs": 139 }, "...", { "date": "2026-12-22", "weight_lbs": 132 } ],
  "actual":  [ { "date": "2026-11-03", "weight_lbs": 139.2 } ],
  "latest_weight_lbs": 139.2, "expected_weight_lbs": 139, "remaining_lbs": -7.2,
  "status": "on_track",
  "projected_finish_date": "2026-12-23"
}
```
`planned` has one point a week plus the target date. `status`: `on_track` (within 1 lb of the plan), `ahead`, `behind` or `reached`. `projected_finish_date` is when the target is reached at the current pace (`null` once reached).

### `GET /meals?hall=&date=&main_only=` ✅
Meals a hall serves on a date, for the dropdown. Returns a list of strings in time-of-day order.
```json
["breakfast", "light lunch", "lunch", "dinner"]
```
`main_only=true` leaves out side menus (salad bar, cereal, beverages, ...). Use it for the dropdown.
Hall names come from the data, e.g. `Ikenberry Dining Center (Ike)`, `Illinois Street Dining Center (ISR)`,
`Pennsylvania Avenue Dining Hall (PAR)`, `Lincoln Avenue Dining Hall (LAR)`.

### `GET /meal-options?hall=&date=` ✅
The meals a hall serves on a date, grouped the way people think of them, for the meal picker. Side menus are left out.
```json
{ "breakfast": ["breakfast"], "lunch": ["light lunch", "lunch"], "dinner": ["dinner"] }
```
A group is left out when the hall doesn't serve it (LAR has no `breakfast`). **If a group has more than one entry** (Ike's `lunch` has `light lunch` and `lunch`), ask the user which one; otherwise go straight to the menu. The data is never merged: send the chosen raw name (e.g. `light lunch`) as `meal` to the other endpoints.

### `GET /halls?date=&meal=` ✅
Hall names that have menu data (on `date`, if given), for the hall dropdown. With `meal` (`breakfast`, `lunch` or `dinner`), only halls that serve that meal that day (`lunch` includes light lunch and kosher lunch; a raw name like `light lunch` matches only itself), so the meal can be picked first. Order: the big dining centers (Ike, ISR, LAR, PAR), then other halls with main meals (Everybody Eats, Kosher Kitchen), then retail shops like 57 North; alphabetical within each group, so the first hall (Ike) is a good default.
```json
["Ikenberry Dining Center (Ike)", "Illinois Street Dining Center (ISR)", "..."]
```

### `GET /menu-items?hall=&date=&meal=&user_id=&include_side_menus=` ✅
The dishes on a menu. With `user_id`, dishes that break that user's allergies or dietary restrictions are removed. Side menus (salad bar, beverages, ...) are skipped unless `include_side_menus=true`.
```json
[{ "id": 1234, "date": "2026-10-08", "hall": "Illinois Street Dining Center (ISR)", "meal": "lunch",
   "station": "Euclid Street Deli", "category": "Salads & Salad Bar", "name": "Cobb Salad",
   "serving_size": 1, "serving_unit": "Cup", "serving_grams": 226,
   "kcal": 500, "protein_g": 38, "carbs_g": 2, "fat_g": 36, "fiber_g": null, "sugar_g": null, "sodium_mg": 1330,
   "allergens": ["Eggs", "Milk"], "is_vegetarian": false, "is_vegan": false }]
```
Nutrients are per ONE serving.

### `GET /users/{id}/meal-target?date=&meal=` ✅
What is left to eat at this meal. What was logged at other meals is subtracted from the day's target; the rest is shared between this meal and every part of the day with nothing logged yet (a meal that wasn't logged counts as still to come, so dinner with nothing logged is about 40% of the day, not all of it); then what is already logged at this meal is subtracted. If protein, carbs and fat together would need more calories than are left, protein is kept and carbs and fat are scaled down to fit (so you never see e.g. 235 kcal with 120 g protein). This is the target the recommendation step is asked to hit.
```json
{
  "date": "2026-10-08", "meal": "dinner",
  "daily_target":       { "kcal": 1450, "protein_g": 127, "carbs_g": 160, "fat_g": 40 },
  "target":             { "kcal": 820,  "protein_g": 70,  "carbs_g": 95,  "fat_g": 24 },
  "meal_budget":        { "kcal": 820,  "protein_g": 70,  "carbs_g": 95,  "fat_g": 24 },
  "consumed_this_meal": { "kcal": 0,    "protein_g": 0,   "carbs_g": 0,   "fat_g": 0 },
  "remaining_day":      { "kcal": 820,  "protein_g": 70,  "carbs_g": 95,  "fat_g": 24 }
}
```
`404` if the user has no goal yet; `422` if `meal` is not breakfast, lunch, light lunch, dinner, kosher lunch or kosher dinner.
Meal weights: breakfast 0.25, lunch / light lunch 0.35, dinner 0.40 (renormalised over this meal and the meals with nothing logged yet).

### `GET /users/{id}/hall-picks?date=&meal=` ✅
Which hall suits the user best for a meal (`breakfast`, `lunch` or `dinner`). At every hall that serves it, the best plate for what the user still needs at that meal is built (same logic as the recommendation), and scored: `match` is 0 to 100, how close the plate gets to the four targets (calories and protein count most). Each hall also gets a **high-protein plate** that stays inside the same calories (about 40% of calories from protein). Allergies and diet are respected. Halls are sorted by `match`; a hall where nothing is left to eat is left out. `404` without a goal, `422` for another meal name.
```json
{
  "date": "2026-10-16", "meal": "lunch",
  "target": { "kcal": 591, "protein_g": 44, "carbs_g": 66, "fat_g": 16 },
  "best_match": "Pennsylvania Avenue Dining Hall (PAR)",
  "best_protein": "Ikenberry Dining Center (Ike)",
  "halls": [{
    "hall": "Pennsylvania Avenue Dining Hall (PAR)", "meal": "lunch", "match": 99,
    "tray":         { "items": [{ "item_id": 1, "name": "...", "servings": 1.5, "kcal": 270, "protein_g": 30, "carbs_g": 2, "fat_g": 12 }],
                      "total": { "kcal": 585, "protein_g": 45, "carbs_g": 65, "fat_g": 18 }, "note": null },
    "high_protein": { "items": [], "total": { "kcal": 580, "protein_g": 60, "carbs_g": 52, "fat_g": 16 }, "protein_share": 41, "note": null }
  }]
}
```
`meal` in each hall is the menu that was compared (when a hall has both `light lunch` and `lunch`, the plain `lunch`). Differences of a point or two between big dining halls are not meaningful; the useful signal is a hall scoring clearly lower (e.g. Everybody Eats has few protein dishes).

### `GET /recommendations/meals?user_id=&hall=&date=&meal=&avoid=` ✅ (D's `recommend()` in `app/recommend.py`)
Recommended dishes for one meal. Without `avoid` the answer is always the same. For a "show me another" button, send `avoid` = the `item_id`s of the tray on screen, comma-separated (e.g. `&avoid=1234,1250,1311`): those dishes are steered away from and a different, similarly good tray comes back. If `recommend()` is missing, errors, or returns something malformed, a simple placeholder in the same shape is returned (with an explanatory `note`), so the page never breaks.
```json
{
  "items": [
    { "item_id": 1234, "name": "Grilled Chicken", "servings": 1.5,
      "kcal": 300, "protein_g": 40, "carbs_g": 2, "fat_g": 12 }
  ],
  "total":  { "kcal": 610, "protein_g": 45, "carbs_g": 60, "fat_g": 18 },
  "target": { "kcal": 600, "protein_g": 45, "carbs_g": 60, "fat_g": 17 },
  "note": null
}
```
- `items[].kcal` etc. are the **totals for that line** (per-serving × `servings`).
- `note` is set when no exact match was possible ("closest option: ...").
- `target` is the `target` from `GET /users/{id}/meal-target`.
- The candidate dishes are the ones from `GET /menu-items?user_id=` (allergies/restrictions already applied); D chooses among them.

### `POST /users/{id}/food-logs` ✅
Log a dish. `date` and `meal` default to the menu item's own.
```json
{ "item_id": 1234, "servings": 1.5 }
```
Returns `201`: `{ "id", "user_id", "date", "meal", "servings", "item_id" }`. `404` if user or item is missing, `422` if `servings <= 0`.

### `GET /users/{id}/food-logs?date=` ✅
That day's logs, same shape as above, as a list.

### `DELETE /users/{id}/food-logs/{log_id}` ✅
Un-check a dish. `204`, or `404` if the log doesn't exist or belongs to another user.

### `POST /users/{id}/weight-logs` ✅
```json
{ "date": "2026-10-08", "weight_lbs": 139.4 }
```
`date` defaults to today. Returns `201` with `{ "id", "user_id", "date", "weight_lbs" }`; `422` if the weight is not positive. The user's current `weight_lbs` follows the most recent weigh-in.

### `GET /users/{id}/weight-logs` ✅
The list, oldest first.

### `GET /users/{id}/progress?date=` ✅
Target vs actual for a day, plus the weight history for the trend chart. `404` if the user has no goal yet.
```json
{
  "date": "2026-10-08",
  "target":    { "kcal": 1450, "protein_g": 127, "carbs_g": 160, "fat_g": 40 },
  "actual":    { "kcal": 1100, "protein_g": 88,  "carbs_g": 130, "fat_g": 35 },
  "remaining": { "kcal": 350,  "protein_g": 39,  "carbs_g": 30,  "fat_g": 5 },
  "over":      { "kcal": 0,    "protein_g": 0,   "carbs_g": 0,   "fat_g": 0 },
  "weight_trend": [ { "date": "2026-10-01", "weight_lbs": 140.2 }, { "date": "2026-10-08", "weight_lbs": 139.4 } ]
}
```
`actual` = sum of (`servings` x per-serving nutrient) over that day's food logs. `remaining` never goes below 0; going over shows up in `over`.

### `GET /exercises?kind=&muscle=&equipment=` ✅
The exercise list (`app/exercises.py`, about 30 moves). Each:
```json
{ "id": "goblet-squat", "name": "Goblet squat", "kind": "strength", "muscles": ["legs", "glutes"],
  "equipment": "Dumbbells", "met": { "light": 3.5, "moderate": 5.0, "hard": 6.0 },
  "how_to": ["Hold one dumbbell upright against your chest...", "..."], "tip": "Keep your heels on the floor...",
  "video_url": "https://www.youtube.com/results?search_query=how+to+do+Goblet+squat+proper+form" }
```
`kind` is `cardio`, `strength` or `mobility`; muscle groups are `legs, glutes, chest, back, shoulders, arms, core, heart`. `how_to` and `video_url` are `null` for machines that explain themselves (treadmill, bike, elliptical, stair climber, track, pool). The video link is a YouTube search, so it never goes stale. No gym is named: the plan says what equipment to use, and the user finds it at whichever gym they go to.

### `GET /users/{id}/workout?date=&intensity=&minutes=&focus=&muscles=&no_equipment=&avoid=` ✅
A workout for the day. Every parameter is optional. Working out is the user's choice: they pick `intensity` (`light`, `moderate` default, `hard`), `minutes` (10-120; default 20 / 35 / 50 by intensity), `muscles` (comma-separated groups), `focus` (`cardio`, `strength`, `mixed`) and `no_equipment=true`. With nothing chosen, the goal sets the focus (lose: cardio, maintain: mixed, gain: strength). Picking only muscles means strength on those groups (`muscles=heart` means cardio). `avoid` (comma-separated exercise ids) is "show me another". The same day gives the same plan.
```json
{
  "date": "2026-10-28", "focus": "strength", "intensity": "moderate", "minutes": 32, "total_kcal": 147,
  "exercises": [
    { "id": "elliptical", "name": "Elliptical", "kind": "cardio", "muscles": ["heart"], "equipment": "Elliptical",
      "sets": null, "reps": null, "minutes": 5, "kcal": 17, "how_to": null, "tip": "...", "video_url": null },
    { "id": "step-up", "name": "Step-up", "kind": "strength", "muscles": ["legs", "glutes"], "equipment": "Bench or box",
      "sets": 3, "reps": "10", "minutes": 4.5, "kcal": 24, "how_to": ["..."], "tip": "...", "video_url": "https://www.youtube.com/results?..." },
    { "id": "stretch", "name": "Full-body stretch", "kind": "mobility", "minutes": 5, "...": "..." }
  ],
  "note": null
}
```
A plan is a 5-minute warm-up (strength and mixed), the main block, and a 5-minute stretch (25 minutes or more). Strength goes round the muscle groups one move each (at most 8 moves; a long session adds sets, then a short cardio finisher). `kcal` = MET x weight (kg) x hours, an estimate; `null` without a weight on the profile. What was eaten never makes the workout harder; it only sets `note` (e.g. "Eat something first, especially before a hard session"). `422` for an unknown choice.

### `POST /users/{id}/workout-logs` ✅
```json
{ "exercise_id": "treadmill", "minutes": 30, "intensity": "moderate", "date": "2026-10-28" }
```
or, for anything not in the list, `{ "name": "Badminton", "minutes": 45, "kcal": 250 }`. `kcal` is worked out from the exercise's MET, the user's weight and the minutes unless sent (e.g. from a watch). `date` defaults to today. Returns `201` with `{ "id", "user_id", "date", "exercise_id", "name", "minutes", "intensity", "kcal" }`; `422` for an unknown `exercise_id`, or a custom one without `kcal`.

### `GET /users/{id}/workout-logs?date=` ✅ / `DELETE /users/{id}/workout-logs/{log_id}` ✅
The list (all days, or one), oldest first. Delete returns `204`.

### `GET /users/{id}/energy?date=` ✅
One day's calories in and out. `404` without a goal, `422` if the profile is missing weight, height, sex or birthdate.
```json
{
  "date": "2026-10-28", "goal_type": "lose", "calorie_goal": 1650,
  "eaten": 1500, "base_burn": 2100, "exercise": 190, "burned": 2290, "net": -790,
  "planned_net": -450, "vs_plan": 340, "status": "ahead",
  "workouts": [ { "id": 1, "name": "Treadmill walk or run", "minutes": 30, "kcal": 190, "...": "..." } ],
  "burn_adjusted": false
}
```
`net` = eaten - burned (negative is a deficit). `vs_plan` is how far the day was from the plan in the goal's direction (positive is ahead: a bigger deficit when losing, a bigger surplus when gaining); it is simply eaten - workouts - calorie goal, so it doesn't depend on the burn estimate. `status`: `ahead`, `on_track` (within 100 kcal), `behind`; for maintain `on_track`, `over`, `under`; `not_logged` (and `eaten: null`) when no food was logged that day. `burn_adjusted` says whether `base_burn` has been corrected from the user's weigh-ins (see below).

### `GET /users/{id}/goal/progress?date=` ✅
How the logged days add up, from the goal's start (or the last 4 weeks without a timeline) to yesterday. Days without food logs don't count.
```json
{
  "goal_type": "lose", "target_date": "2026-12-20", "since": "2026-10-20", "days": 8, "days_logged": 6,
  "ahead_kcal": 1750, "ahead_lbs": 0.5, "status": "ahead", "days_earlier": 3, "projected_finish_date": "2026-12-17",
  "message": "You are 1750 kcal ahead of plan over 6 logged days, about 0.5 lb. At this rate you finish about 3 days early.",
  "weight": { "from_weight_lbs": 158.6, "from_date": "2026-10-26", "estimated_weight_lbs": 158.1 },
  "scale": { "status": "on_track", "latest_weight_lbs": 158.4, "expected_weight_lbs": 158.9, "remaining_lbs": 18.4, "projected_finish_date": "2026-12-22" },
  "calibration": { "factor": 0.94, "burn_estimate": 1975, "days_used": 21, "message": "From your weigh-ins and logs over 21 days, you seem to burn about 1975 kcal a day, 125 less than the formula. The estimates below use that." }
}
```
How the logs and the scale fit together (`app/energy.py`): the logs give the day-to-day picture and the scale corrects it. `weight` is the latest smoothed weigh-in (the average of the readings in the week before it) plus the calories logged since. Once there are two weeks between weigh-ins with food logged on most days, the weight really lost or gained shows how much this person burns; `calibration.factor` (0.8-1.2, pulled toward 1 with little data) then scales the daily burn everywhere. `scale` is the weigh-in-based status from `GET .../goal/timeline` (`null` without a timeline). `days_earlier` and `projected_finish_date` (from the logs) only for a timeline goal. Rough estimates (about 3,500 kcal per lb), not medical advice.

### `GET /events?start=&days=&fitness_only=&q=` ✅
Upcoming events from the campus [Recreation, Health & Wellness calendar](https://calendars.illinois.edu/list/637) (read as iCal, cached for an hour). By default the exercise ones (skating, classes, runs, ...) in the next 7 days; `fitness_only=false` adds the other wellness events; `q` searches the title, place and description; `days` 1-31. No login needed.
```json
{ "start": "2026-10-28", "days": 7, "source": "https://calendars.illinois.edu/list/637",
  "events": [ { "title": "Lunch Skate", "start": "2026-10-28T11:15:00", "end": "2026-10-28T12:30:00", "all_day": false,
                "location": "Ice Arena 406 E. Armory Ave. Champaign, IL 61820", "description": "...", "url": "https://calendars.illinois.edu/detail/637/..." } ] }
```
`503` if the campus calendar can't be reached and nothing is cached. Student club (RSO) events aren't included: they are in a system that needs a login.

## Who builds what
- **C:** every endpoint above, deployment (Render, `DATABASE_URL` env var).
- **B:** owns `app/nutrition.py` (a working baseline is in PR #9): daily targets, per-meal split, cross-meal adjustment, progress. Timelines and their safety limits are in `app/timeline.py`. Still open for B: tuning the meal weights.
- **D:** `recommend(target, items) -> {items, total, note}` as a plain function; C calls it.
- **A:** menu data (`menuitem` table, kept fresh), `GET /halls`, `GET /menu-items`, end-to-end tests; workouts (`app/exercises.py`, `app/workout.py`, on top of D's `recommend_workout()` template), workout logs, the energy balance and weigh-in calibration (`app/energy.py`), campus events (`app/events.py`).
- **Frontend:** build against this document with mock data, switch the base URL when the backend is ready.
