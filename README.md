# Plate Plan

**Know what to eat before you reach the dining hall.**

Plate Plan is a nutrition planner for University of Illinois Urbana-Champaign students who eat in the dining halls. It reads the real campus menus every week, sets daily calorie and macro targets for your goal, and tells you which dishes to take, and how much of each, for your next meal. It also plans workouts and tracks food, exercise and weight in one place.

| | Link |
|---|---|
| **Live app** | https://plate-plan-group6.vercel.app |
| **Live API (interactive docs)** | https://fa26-group6.onrender.com/docs |
| **API specification** | [`Docs/API.md`](Docs/API.md) |
| **How to run the frontend** | [`Docs/RUN.md`](Docs/RUN.md) |

> The API runs on a free server that sleeps when idle. The first request after a quiet spell can take up to a minute; open the API docs link first to wake it.

Built by a team of six. **I (Valerie Yu) built the data and backend side**: the menu scraper and data pipeline, the database, meal targets and menu filtering, dining-hall picks, workouts, the energy balance with weigh-in calibration, campus events, account features and most of the backend tests. I made 37 of the project's 92 commits, the most on the team. Details in [My contributions](#my-contributions).

---

## What it does

**Plan a meal**
- Sign up with height, weight, age, sex, activity level, allergies and diet (vegetarian, vegan, ...).
- Pick a goal: lose, maintain or gain weight, optionally with a target weight and date (the pace is capped at a safe rate).
- Get daily calorie, protein, carb and fat targets, split across the meals you actually eat (for example, only lunch and dinner).
- Choose a meal and see which dining hall fits it best, then get a recommended plate: specific dishes and servings that add up to what is left for that meal. "Show me another" gives a different plate.
- Allergens and diet are filtered out automatically.
- If one meal was small, the meals still to come get a bigger share of the day.

**Track**
- Log the dishes you ate with one tap, or quick-add food from anywhere else (name and calories).
- Log weigh-ins. The app compares your real weight with the predicted one and adjusts your calorie target.
- See each day's calories eaten against calories burned, and progress toward your goal weight.

**Work out**
- Get a workout plan for the muscle groups, length and intensity you choose, with or without gym equipment. Each move has how-to steps, a tip and a video link.
- Log workouts. Calories burned are estimated from your body weight and count toward the day's balance.
- See upcoming campus fitness events, taken from the university calendar.

**Account**
- Log in securely, edit your profile, change your password or delete your account and all its data.

## How it works

```
UIUC EatSmart menus ──► scraper ──► PostgreSQL (Neon) ◄──► FastAPI backend ◄──► React frontend
     (12 dining units)     (weekly)                           (Render)              (Vercel)
```

| Part | Tech | Folder |
|---|---|---|
| Frontend | React 19, Vite, Tailwind CSS | [`Project/frontend`](Project/frontend) |
| Backend API | Python, FastAPI, SQLModel, JWT login | [`Project/backend/app`](Project/backend/app) |
| Database | PostgreSQL on Neon (SQLite for local development) | tables in [`app/models.py`](Project/backend/app/models.py) |
| Menu scraper | requests, BeautifulSoup | [`Project/backend/scraper`](Project/backend/scraper) |
| Tests | pytest, 270+ tests | [`Project/backend/tests`](Project/backend/tests) |

Main backend modules:

| File | What it does |
|---|---|
| `nutrition.py` | Daily targets (BMR × activity) and the per-meal split |
| `timeline.py` | Target weight and date, with safe-pace limits |
| `dietary.py` | Allergy and diet filters |
| `recommend.py` | Chooses dishes and servings for a meal (beam search) and the workout template |
| `picks.py` | Scores each dining hall for your next meal |
| `exercises.py`, `workout.py` | Exercise library and workout plans |
| `energy.py` | Daily energy balance, goal progress, calibration from weigh-ins |
| `events.py` | Campus fitness events from the university calendar |
| `auth.py` | Sign-up, login and access control |

## Menu data

Menus come from [UIUC EatSmart](https://eatsmart.housing.illinois.edu/NetNutrition/46). The scraper walks hall → station → date and meal → dish → nutrition label, cleans each dish and saves it. It covers 12 dining units: Ikenberry, ISR, PAR, LAR, Field of Greens, Kosher Kitchen, TerraByte, InfiniTEA, Urbana South Market, 57 North, Caffeinator and Everybody Eats.

- About 60,000 dishes are loaded so far (fall 2026 semester). Menus are published about three weeks ahead and are refreshed by hand weekly.
- Only main meals (breakfast, lunch, dinner) are recommended. Salad bar, cereal, drinks and condiments are stored but not recommended.
- Dishes missing calories or macros are skipped, and "NA" values are stored as empty, not zero.

```sh
cd Project/backend
python -m scraper.menu_scraper --days 14                  # today + 13 days, all halls
python -m scraper.menu_scraper --days 3 --halls 1 11 --dry-run --json out.json   # try it without saving
python -m scraper.copy_menu_to_db                          # copy local menus to the shared DB (needs DATABASE_URL)
```

## Run it locally

You need Python 3.12+ and Node.js 20+.

**Backend** (from the repository root):

```sh
cd Project/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs. With nothing configured, the backend uses a local SQLite file (`nutrition.db`); fill it with the scraper above. To use the shared PostgreSQL database, put `DATABASE_URL=...` in `Project/backend/.env`. **Never commit it**: `.env` and `*.db` are in `.gitignore`.

**Frontend** (in a second terminal):

```sh
cd Project/frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend talks to the local backend by default; to use another one, copy `.env.example` to `.env.local` and change `VITE_API_URL`. The backend only accepts the frontend on port 5173 or 3000.

**Tests:**

```sh
cd Project/backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

## Deployment

- **Backend:** Render redeploys automatically on every push to `master`. `DATABASE_URL` (and the JWT secret) are set in Render's environment settings.
- **Frontend:** deployed by hand from the Vercel project owner's computer. Always pull first, or old code gets deployed:
  ```sh
  git switch master && git pull
  cd Project/frontend && npx vercel deploy --prod
  ```

## API overview

Full request and response examples are in [`Docs/API.md`](Docs/API.md). JSON, ISO dates, pounds and inches, nutrients in grams per one serving.

| Area | Endpoints |
|---|---|
| Account | `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `POST /auth/change-password`, `GET/PATCH/DELETE /users/{id}`, `PUT /users/{id}/meals` |
| Goal | `PUT/GET /users/{id}/goal`, `POST /users/{id}/goal/preview`, `GET /users/{id}/goal/timeline`, `GET /users/{id}/goal/progress` |
| Menus | `GET /halls`, `GET /meal-options`, `GET /meals`, `GET /menu-items` |
| Meal planning | `GET /users/{id}/meal-target`, `GET /users/{id}/hall-picks`, `GET /recommendations/meals` |
| Tracking | `POST/GET/DELETE /users/{id}/food-logs`, `POST/GET/DELETE /users/{id}/weight-logs`, `GET /users/{id}/progress`, `GET /users/{id}/energy` |
| Workouts | `GET /exercises`, `GET /users/{id}/workout`, `POST/GET/DELETE /users/{id}/workout-logs`, `GET /events` |

## My contributions

Everything below is my own work, in [`Project/backend`](Project/backend) unless noted.

**Menu data pipeline**
- Wrote the EatSmart scraper ([`scraper/menu_scraper.py`](Project/backend/scraper/menu_scraper.py)) from scratch: discovers halls, stations, dates and meals, reads every dish's nutrition label, parses serving sizes, separates allergens from diet tags, skips incomplete dishes, and upserts into the database without duplicates. Each hall is saved as it finishes, so a dropped connection loses at most one hall.
- Designed the `menuitem` table and the "recommendable" flag that keeps salad bars, drinks and condiments out of recommendations.
- Wrote the script that copies menus into the production PostgreSQL database in one batch, and kept the live data fresh all semester: about 60,000 dishes from 12 dining units.
- Wrote a sample menu dataset so the recommender could be developed and tested without a database.

**Backend foundations**
- Wrote the API specification ([`Docs/API.md`](Docs/API.md)) the frontend was built against, and many of its endpoints: goal targets, halls and menus, meal targets, progress, weight logs and undoing a food log.
- Wrote the allergy and diet filters ([`app/dietary.py`](Project/backend/app/dietary.py)).
- Wrote the nutrition baseline: daily calorie and macro targets, the per-meal split, carrying what was eaten at one meal over to the meals still to come, and fitting macros inside the calorie target with protein first.
- Added "choose which meals you eat": the day's calories are shared only between the meals a user actually eats.

**Meal recommendations**
- Added meal-sense rules on top of the beam-search recommender (no sauces or condiments as a dish, every dish worth eating, at most one dessert, at least two dishes, no duplicates, at most two servings per dish) and "show me another".
- Built the dining-hall picks ([`app/picks.py`](Project/backend/app/picks.py)): a 0-100 match score per hall for the next meal and a high-protein plate per hall, plus the frontend card for it.
- Built the meal-first flow in the frontend: pick the meal, then the hall, then log or swap the recommended tray.

**Workouts and energy**
- Wrote the exercise library (30 moves with how-to steps, tips and video links) and the workout planner ([`app/exercises.py`](Project/backend/app/exercises.py), [`app/workout.py`](Project/backend/app/workout.py)): warm-up, main block and cool-down for chosen muscle groups, length and intensity, with or without equipment, balanced across movement patterns so a plan doesn't repeat the same move.
- Wrote workout logging with calories burned estimated from body weight.
- Wrote the daily energy balance and goal progress ([`app/energy.py`](Project/backend/app/energy.py)), including calibration: real weigh-ins are compared with the predicted weight and the calorie target is adjusted (within safe limits). Workouts already covered by the user's activity level aren't counted twice.
- Wrote the campus fitness events feed ([`app/events.py`](Project/backend/app/events.py)) from the university calendar.

**Accounts and data quality**
- Added quick-add food logs, deleting weigh-ins (the plan is recalculated), profile editing, password change and account deletion.
- Made "today" follow campus (Chicago) time and limited logging to today and the past seven days.
- Ran full end-to-end walkthroughs of the live app and fixed what they found.

**Testing**
- Wrote most of the 270+ backend tests: scraper parsing, nutrition and meal targets, recommendations on real menus, workouts, energy balance, accounts and end-to-end API flows.

## Team

Built with:

- Valerie Yu ([@Valerieyu77](https://github.com/Valerieyu77))
- Grace ([@gracee-s](https://github.com/gracee-s))
- Andrew ([@AndrewYYX](https://github.com/AndrewYYX))
- Mark ([@Mark-dot-create](https://github.com/Mark-dot-create))
- Sacha ([@Sachavk8](https://github.com/Sachavk8))
- Uzair ([@uzairs2](https://github.com/uzairs2)), project manager

## Working together

- Branch off `master`, push your branch and open a pull request; a teammate reviews it before it is merged.
- Merge with **Create a merge commit** (not squash or rebase).
- Announce changes to shared things (table columns, API shapes, `Docs/API.md`) with the team first.
- Keep secrets out of the repository: no database URLs, passwords or keys in code or commits.
