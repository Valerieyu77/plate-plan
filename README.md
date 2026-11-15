# Plate Plan

**Know what to eat before you reach the dining hall.**

Plate Plan is a nutrition planner for University of Illinois Urbana-Champaign students who eat in the dining halls. It reads the real campus menus every week, sets daily calorie and macro targets for your goal, and tells you which dishes to take, and how much of each, for your next meal. It also plans workouts and tracks food, exercise and weight in one place.

| | Link |
|---|---|
| **Live app** | https://plate-plan-group6.vercel.app |
| **Live API (interactive docs)** | https://fa26-group6.onrender.com/docs |
| **API specification** | [`Docs/API.md`](Docs/API.md) |
| **How to run the frontend** | [`Docs/RUN.md`](Docs/RUN.md) |
| **Project plan (MVP)** | [MVP document](https://docs.google.com/document/d/1mmSCIEQjmluVGSqgNbrygXDC9vFZJ26P/edit?pli=1) |

> The API runs on a free server that sleeps when idle. The first request after a quiet spell can take up to a minute; open the API docs link first to wake it.

CS 196 (Fall 2026), Group 6. Team: Valerie Yu ([@Valerieyu77](https://github.com/Valerieyu77)), Grace ([@gracee-s](https://github.com/gracee-s)), Andrew ([@AndrewYYX](https://github.com/AndrewYYX)), Mark ([@Mark-dot-create](https://github.com/Mark-dot-create)), Sacha ([@Sachavk8](https://github.com/Sachavk8)). Project manager: Uzair ([@uzairs2](https://github.com/uzairs2)).

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

## Team

| Who | Role | Main work |
|---|---|---|
| Valerie Yu | Data and backend | Menu scraper and data, database, menu and hall endpoints, workouts, energy balance and weigh-in calibration, campus events, account features, tests |
| Grace | API, deployment, auth | Endpoints, Render deployment, login (JWT), goal timelines |
| Andrew, Mark | Frontend | React app: meal planning, tracking, workouts, settings |
| Sacha | Recommendation engine | Beam-search plate recommender, workout template |
| Uzair | Project manager | Planning and coordination |

## Working together

- Branch off `master`, push your branch and open a pull request; a teammate reviews it before it is merged.
- Merge with **Create a merge commit** (not squash or rebase).
- Announce changes to shared things (table columns, API shapes, `Docs/API.md`) in the group chat first.
- Keep secrets out of the repository: no database URLs, passwords or keys in code or commits.
