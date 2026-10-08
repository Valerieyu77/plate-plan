# API specification (prototype)

Draft for the whole team to confirm. Frontend can build against this with mock data now; backend
switches mock to real without changing the shapes. If you need a change, post it in the group chat
first and update this file in the same PR.

Base URL: `http://127.0.0.1:8000` locally. Interactive docs: `/docs`.

## Conventions
- JSON everywhere. Dates are ISO strings: `"2026-10-08"`.
- Units: weight in **lbs**, height in **inches**, nutrients in **g** (sodium in mg), energy in **kcal**.
- All nutrient values on a menu item are **per ONE serving**.
- No login in the prototype: sign-up returns a `user_id`; the frontend keeps it (e.g. in localStorage) and puts it in the URL.
- Errors: `404` not found, `409` duplicate email, `422` invalid input. Body: `{"detail": "..."}`.
- CORS must be enabled on the backend so the browser can call it (`CORSMiddleware`, allow the frontend origin).

Status: ✅ built and merged, 🟡 build with mock data first, ⬜ not started.

## User flow → endpoints

| Step in the app | Endpoint |
|---|---|
| Sign up with body info | `POST /users` ✅ |
| Set a goal, get daily targets | `PUT /users/{id}/goal` 🟡 |
| Choose hall + date, see which meals exist | `GET /meals` ✅ |
| Get recommended dishes for that meal | `GET /recommendations/meals` 🟡 |
| Check off what was eaten | `POST /users/{id}/food-logs` ✅ (undo: `DELETE`, ⬜) |
| Log weight | `POST /users/{id}/weight-logs` ⬜ |
| Progress page: target vs actual, weight trend | `GET /users/{id}/progress` 🟡 |

## Endpoints

### `POST /users` ✅
Create a user. Returns `201` with the user (including `id`), `409` if the email exists.
```json
{
  "name": "Val", "email": "val@example.com",
  "weight_lbs": 140, "height_in": 64, "gender": "female",
  "birthdate": "2004-05-17", "activity_level": "moderate",
  "allergies": ["Milk", "Peanuts"],
  "dietary_restrictions": ["vegetarian"]
}
```
- `allergies` names: Milk, Eggs, Fish, Shellfish, Peanuts, Tree Nuts, Soy, Wheat, Gluten, Sesame, Corn, Coconut, Sulfites, MSG, Red Dye.
- `dietary_restrictions`: vegetarian, vegan, kosher, halal, jain, no pork, no alcohol, no gelatin. (See `app/dietary.py`.)
- `activity_level`: **TBD by B**, suggested `sedentary | light | moderate | active | very_active`.

### `GET /users/{id}` ✅
Returns the same shape as above plus `id`.

### `PUT /users/{id}/goal` 🟡 (B computes, C exposes)
Sets the goal and returns the computed daily targets.
```json
// request
{ "target_weight_lbs": 130, "weeks": 12 }
// response
{
  "user_id": 1, "target_weight_lbs": 130,
  "calorie_goal": 1650, "protein_goal_g": 120, "carb_goal_g": 170, "fat_goal_g": 55,
  "warning": null, "suggested_weeks": null
}
```
If the goal is unsafe (more than ~1% of body weight per week, or below the minimum intake), the
targets are for the safe pace and `warning` explains it, with `suggested_weeks` set.
**Open question (B + C):** `Goal.target_date` was removed, so the timeline is passed as `weeks` here and not stored. Confirm.

### `GET /users/{id}/goal` ⬜
Returns the stored goal (same fields as the response above). `404` if none.

### `GET /meals?hall=&date=&main_only=` ✅
Meals a hall serves on a date, for the dropdown. Returns a list of strings in time-of-day order.
```json
["breakfast", "light lunch", "lunch", "dinner"]
```
`main_only=true` leaves out side menus (salad bar, cereal, beverages, ...). Use it for the dropdown.
Hall names come from the data, e.g. `Ikenberry Dining Center (Ike)`, `Illinois Street Dining Center (ISR)`,
`Pennsylvania Avenue Dining Hall (PAR)`, `Lincoln Avenue Dining Hall (LAR)`.

### `GET /halls` ⬜
List of hall names that have data, so the frontend doesn't hardcode them.
```json
["Ikenberry Dining Center (Ike)", "Illinois Street Dining Center (ISR)", "..."]
```

### `GET /menu-items?hall=&date=&meal=` ⬜
The dishes on a menu, for browsing and for logging a dish by hand. `main_only` not needed: filter by `meal`.
```json
[{ "id": 1234, "name": "Cobb Salad", "category": "Salads & Salad Bar", "station": "Euclid Street Deli",
   "serving_size": 1, "serving_unit": "Cup", "serving_grams": 226,
   "kcal": 500, "protein_g": 38, "carbs_g": 2, "fat_g": 36,
   "allergens": ["Eggs", "Milk"], "is_vegetarian": false, "is_vegan": false }]
```

### `GET /recommendations/meals?user_id=&hall=&date=&meal=` 🟡 (B + D compute, C exposes)
Recommended dishes for one meal. Returns hard-coded mock data at first.
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
- `target` is this meal's share of the daily target, after subtracting what the user already logged today.
- Allergies/restrictions are applied before the algorithm runs (B filters, D chooses).

### `POST /users/{id}/food-logs` ✅
Log a dish. `date` and `meal` default to the menu item's own.
```json
{ "item_id": 1234, "servings": 1.5 }
```
Returns `201`: `{ "id", "user_id", "date", "meal", "servings", "item_id" }`. `404` if user or item is missing, `422` if `servings <= 0`.

### `GET /users/{id}/food-logs?date=` ✅
That day's logs, same shape as above, as a list.

### `DELETE /users/{id}/food-logs/{log_id}` ⬜
Un-check a dish. `204`.

### `POST /users/{id}/weight-logs` ⬜
```json
{ "date": "2026-10-08", "weight_lbs": 139.4 }
```
Returns `201` with the stored row. `GET /users/{id}/weight-logs` returns the list, oldest first.

### `GET /users/{id}/progress?date=` 🟡 (B computes, C exposes)
Target vs actual for a day, plus the weight trend, for the progress page.
```json
{
  "date": "2026-10-08",
  "target":    { "kcal": 1650, "protein_g": 120, "carbs_g": 170, "fat_g": 55 },
  "actual":    { "kcal": 1210, "protein_g": 88,  "carbs_g": 130, "fat_g": 40 },
  "remaining": { "kcal": 440,  "protein_g": 32,  "carbs_g": 40,  "fat_g": 15 },
  "weight_trend": [ { "date": "2026-10-01", "weight_lbs": 140.2 }, { "date": "2026-10-08", "weight_lbs": 139.4 } ]
}
```
`actual` = sum of (`servings` × per-serving nutrient) over that day's food logs.

## Who builds what
- **C:** every endpoint above, CORS, deployment (Render, `DATABASE_URL` env var).
- **B:** target and progress calculations as plain functions (suggested `app/nutrition.py`); C calls them.
- **D:** `recommend(target, items) -> {items, total, note}` as a plain function; C calls it.
- **A:** menu data (`menuitem` table, kept fresh), `GET /halls` and `GET /menu-items` if C wants them, end-to-end tests.
- **Frontend:** build against this document with mock data, switch the base URL when the backend is ready.
