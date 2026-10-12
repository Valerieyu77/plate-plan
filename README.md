# Group 6
Group Name: TEAM_NAME

[MVP Link](https://docs.google.com/document/d/1mmSCIEQjmluVGSqgNbrygXDC9vFZJ26P/edit?pli=1)

Team Members: pinkiey2, gracees7, markw8, ay29


Project Manager: uzairs2

---

## What this project does

Recommends specific UIUC dining hall dishes, and how much of each, based on a user's weight goal.

1. Sign up with height, weight, age (birthdate), sex, activity level, allergies and dietary restrictions
2. Pick a goal: lose, maintain or gain
3. The app calculates daily calorie, protein, carb and fat targets
4. Pick a dining hall and a meal (e.g. ISR lunch) and get recommended dishes that fit what is left for that meal
5. Check off what you ate; the app logs it
6. The progress page shows target vs actual, and your weight trend

## How it fits together

```
UIUC EatSmart menus  ->  scraper  ->  PostgreSQL (Neon)  <->  FastAPI backend  <->  React frontend
```

| Part | Folder | What it is |
|---|---|---|
| Frontend | `Project/frontend` | React + Vite app (Plate Plan design) |
| Backend API | `Project/backend/app` | FastAPI + SQLModel |
| Menu scraper | `Project/backend/scraper` | Collects dining hall menus and nutrition into the database |
| Tests | `Project/backend/tests` | pytest |
| Docs | `Docs` | API specification (`API.md`), how to run the frontend (`RUN.md`) |

## Getting started

### Backend

You need Python 3 (3.12 or newer is a safe choice). From the repository root:

```sh
cd Project/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for the interactive API page.

**Database.** With nothing configured, the backend uses a local SQLite file (`nutrition.db`, empty at first). To use the shared PostgreSQL database instead, set `DATABASE_URL`, either in your terminal (`export DATABASE_URL='...'`) or in a file `Project/backend/.env` containing `DATABASE_URL=...`. Ask a teammate for the value. **Never commit the connection string**: `.env` and `*.db` are already in `.gitignore`.

### Frontend

```sh
cd Project/frontend
npm install
npm run dev
```

The frontend currently runs on sample data; connecting it to the API is in progress. See `Docs/RUN.md`.

### Tests

```sh
cd Project/backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

## API

The full specification, with request and response examples for every endpoint, is in [`Docs/API.md`](Docs/API.md). Conventions: JSON, ISO dates (`2026-10-08`), weight in lbs, height in inches, nutrients in grams (sodium in mg), and all menu nutrients are per **one** serving.

| Endpoint | Purpose | Status |
|---|---|---|
| `POST /users`, `GET /users/{id}` | Sign up and read a profile | Done |
| `PUT /users/{id}/goal`, `GET /users/{id}/goal` | Pick lose / maintain / gain, get daily targets | Done |
| `GET /halls`, `GET /meals` | Halls with data, and the meals a hall serves on a date | Done |
| `GET /menu-items` | Dishes on a menu, filtered for a user's allergies and diet | Done |
| `GET /users/{id}/meal-target` | What is left to eat at this meal (adjusted for what was already logged) | Done |
| `POST/GET/DELETE /users/{id}/food-logs` | Log, list and un-check eaten dishes | Done |
| `POST/GET /users/{id}/weight-logs` | Log and list weigh-ins | Done |
| `GET /users/{id}/progress` | Target vs actual for a day, plus weight history | Done |
| `GET /recommendations/meals` | Recommended dishes for a meal | Not started |

## Menu data

Menus come from the UIUC EatSmart site (`eatsmart.housing.illinois.edu/NetNutrition`). The scraper walks hall -> station -> date and meal -> dish -> nutrition label, cleans each dish and saves it to the `menuitem` table. It covers all 12 dining units, which publish menus about three weeks ahead.

```sh
cd Project/backend
python -m scraper.menu_scraper --days 14          # today + 13 days, all halls, saved to the database
python -m scraper.menu_scraper --days 3 --halls 1 11 --dry-run --json out.json   # try it without saving
```

- Running it again updates existing rows instead of duplicating them. Each hall is saved as soon as it finishes.
- To copy a local database into the shared one: `python -m scraper.copy_menu_to_db` (with `DATABASE_URL` set).
- `data/menu_sample.json` is a small snapshot (recommendable dishes only, Oct 7-9 2026) for developing the recommendation function without a database.
- A weekly GitHub Actions job is set up in `.github/workflows/scrape-menus.yml`, but GitHub currently refuses to start workflows for this organization (a billing / spending-limit message), so for now the scraper is run by hand about once a week.

Things worth knowing about the data:
- `meal` is the site's own menu name, lowercase: `breakfast`, `lunch`, `light lunch`, `dinner`, and also `salad bar`, `beverages`, and so on. Not every hall serves every meal (Ike has a light lunch, LAR has no breakfast), so list a hall's meals with `GET /meals` instead of hardcoding them.
- `is_recommendable` is true only for main meals. Side menus are stored but marked false.
- `allergens` holds the site's tags. Which ones count as real allergens (Milk, Peanuts, ...) and which are just labels (Kosher, Halal, Pork, ...) is defined in `app/dietary.py`.
- Dishes missing calories or any macro are skipped. Values the site marks "NA" are stored as empty, not zero.

## Database tables

Defined in `Project/backend/app/models.py`.

| Table | What it stores |
|---|---|
| `user` | Profile: height, weight (lbs/in), sex, birthdate, activity level, allergies, dietary restrictions |
| `goal` | One row per user: daily calorie / protein / carb / fat targets |
| `weightlog` | Weigh-ins over time |
| `foodlog` | What a user ate: dish, servings, date, meal |
| `menuitem` | Every scraped dish with per-serving nutrition, tags and serving size |

## Working together

- Branch off `master`, push your branch, and open a pull request. Another teammate looks at it before it is merged.
- Merge with **Create a merge commit** (not squash or rebase), so branches built on each other stay in sync.
- Announce changes to shared things (table columns, API shapes, `Docs/API.md`) in the group chat first.
- Keep secrets out of the repository: no database URLs, passwords or keys in code or commits.

## Roles

| Role | Responsibility |
|---|---|
| A, Data | Project setup, menu scraping, data cleaning, database, testing |
| B, Nutrition targets | Daily and per-meal targets, dietary filtering, progress calculations |
| C, API / integration | API endpoints, deployment, working with the frontend |
| D, Recommendation engine | Choosing dishes for a meal (see `app/recommend.py` once merged) |

The full plan, with tools and task lists, is in the MVP document linked at the top.
