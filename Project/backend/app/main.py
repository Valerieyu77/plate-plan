from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .models import (
    FoodLog, FoodLogCreate, FoodLogPublic, Goal, GoalCreate, GoalPublic, MenuItem, MenuItemPublic, User, UserCreate,
    UserPublic, WeightLog, WeightLogCreate, WeightLogPublic,
)
from .dietary import allowed_for_user
from .recommend import recommend
from .nutrition import (
    add_nutrients, daily_targets, day_progress, goal_to_targets, item_nutrients, meal_target, zero_nutrients,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: create any tables that don't exist yet
    create_db_and_tables()
    yield


app = FastAPI(title="UIUC Dining Nutrition API", lifespan=lifespan)

# Let the browser frontend call this API from another address (local dev server or Vercel).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints that list this as a parameter get a database session automatically
SessionDep = Annotated[Session, Depends(get_session)]


@app.post("/users", response_model=UserPublic, status_code=201)
def create_user(user: UserCreate, session: SessionDep):
    existing = session.exec(select(User).where(User.email == user.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    db_user = User.model_validate(user)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)  # loads the auto-generated id
    return db_user


@app.get("/users/{user_id}", response_model=UserPublic)
def read_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Main meals in the order they happen during the day; anything else (salad bar, cereal, ...) sorts after
MEAL_ORDER = ["breakfast", "light lunch", "lunch", "kosher lunch", "dinner", "kosher dinner"]


@app.get("/meals", response_model=list[str])
def list_meals(hall: str, date: date, session: SessionDep, main_only: bool = False):
    """Meal values a hall serves on a date, for the meal dropdown (e.g. Ike has "light lunch", LAR has no breakfast).

    main_only=true leaves out side menus like "salad bar" and "beverages".
    """
    query = select(MenuItem.meal).where(MenuItem.hall == hall, MenuItem.date == date).distinct()
    if main_only:
        query = query.where(MenuItem.is_recommendable)
    meals = session.exec(query).all()
    return sorted(meals, key=lambda m: (MEAL_ORDER.index(m) if m in MEAL_ORDER else len(MEAL_ORDER), m))


@app.post("/users/{user_id}/food-logs", response_model=FoodLogPublic, status_code=201)
def create_food_log(user_id: int, log: FoodLogCreate, session: SessionDep):
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    item = session.get(MenuItem, log.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db_log = FoodLog(
        user_id=user_id,
        item_id=item.id,
        servings=log.servings,
        date=log.date or item.date,
        meal=log.meal or item.meal,
    )
    session.add(db_log)
    session.commit()
    session.refresh(db_log)
    return db_log


@app.get("/users/{user_id}/food-logs", response_model=list[FoodLogPublic])
def list_food_logs(user_id: int, date: date, session: SessionDep):
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return session.exec(select(FoodLog).where(FoodLog.user_id == user_id, FoodLog.date == date)).all()


@app.put("/users/{user_id}/goal", response_model=GoalPublic)
def set_goal(user_id: int, goal: GoalCreate, session: SessionDep):
    """Pick lose / maintain / gain; the daily calorie and macro targets are calculated and saved."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        targets = daily_targets(user, goal.goal_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    warning = targets.pop("warning")
    db_goal = session.get(Goal, user_id) or Goal(user_id=user_id)
    for key, value in targets.items():
        setattr(db_goal, key, value)
    session.add(db_goal)
    session.commit()
    session.refresh(db_goal)
    return GoalPublic(**db_goal.model_dump(), warning=warning)


@app.get("/users/{user_id}/goal", response_model=GoalPublic)
def read_goal(user_id: int, session: SessionDep):
    goal = session.get(Goal, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="No goal set for this user")
    return goal


# ---------- Menus ----------

@app.get("/halls", response_model=list[str])
def list_halls(session: SessionDep, date: date | None = None):
    """Halls that have menu data (on `date`, if given), for the hall dropdown."""
    query = select(MenuItem.hall).distinct()
    if date:
        query = query.where(MenuItem.date == date)
    return sorted(session.exec(query).all())


@app.get("/menu-items", response_model=list[MenuItemPublic])
def list_menu_items(
    hall: str, date: date, session: SessionDep,
    meal: str | None = None, user_id: int | None = None, include_side_menus: bool = False,
):
    """
    The dishes on a menu. With `user_id`, dishes that break the user's allergies or dietary
    restrictions are left out. Side menus (salad bar, beverages, ...) are skipped unless asked for.
    """
    query = select(MenuItem).where(MenuItem.hall == hall, MenuItem.date == date)
    if meal:
        query = query.where(MenuItem.meal == meal.strip().lower())
    if not include_side_menus:
        query = query.where(MenuItem.is_recommendable)
    items = session.exec(query.order_by(MenuItem.station, MenuItem.category, MenuItem.name)).all()
    if user_id is not None:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        items = [i for i in items if allowed_for_user(i, user)]
    return items


# ---------- Food logs: undo ----------

@app.delete("/users/{user_id}/food-logs/{log_id}", status_code=204)
def delete_food_log(user_id: int, log_id: int, session: SessionDep):
    log = session.get(FoodLog, log_id)
    if not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="Food log not found")
    session.delete(log)
    session.commit()


# ---------- Weight logs ----------

@app.post("/users/{user_id}/weight-logs", response_model=WeightLogPublic, status_code=201)
def create_weight_log(user_id: int, entry: WeightLogCreate, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    day = entry.date or date.today()
    log = WeightLog(user_id=user_id, date=day, weight_lbs=entry.weight_lbs)
    session.add(log)

    # The user's current weight (used for targets) follows the most recent weigh-in
    latest = session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date.desc())).first()
    if latest is None or day >= latest.date:
        user.weight_lbs = entry.weight_lbs
        session.add(user)
    session.commit()
    session.refresh(log)
    return log


@app.get("/users/{user_id}/weight-logs", response_model=list[WeightLogPublic])
def list_weight_logs(user_id: int, session: SessionDep):
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date, WeightLog.id)).all()


# ---------- Targets and progress ----------

def _consumed_by_meal(session: Session, user_id: int, day: date) -> dict[str, dict]:
    """{meal: nutrients eaten} from the user's food logs for a day. Logs without a menu item are skipped."""
    rows = session.exec(
        select(FoodLog, MenuItem)
        .join(MenuItem, MenuItem.id == FoodLog.item_id)
        .where(FoodLog.user_id == user_id, FoodLog.date == day)
    ).all()
    by_meal: dict[str, dict] = {}
    for log, item in rows:
        total = by_meal.setdefault(log.meal, zero_nutrients())
        by_meal[log.meal] = add_nutrients(total, item_nutrients(item, log.servings))
    return by_meal


def _daily_targets_or_404(session: Session, user_id: int) -> dict:
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    goal = session.get(Goal, user_id)
    if not goal or not goal.calorie_goal:
        raise HTTPException(status_code=404, detail="No goal set for this user; call PUT /users/{id}/goal first")
    return goal_to_targets(goal)


@app.get("/users/{user_id}/meal-target")
def read_meal_target(user_id: int, date: date, meal: str, session: SessionDep):
    """
    What is left to eat at this meal: the day's target minus what was logged at earlier meals,
    shared between this meal and the ones after it, minus what is already logged at this meal.
    This is what the recommendation step is asked to hit.
    """
    daily = _daily_targets_or_404(session, user_id)
    try:
        result = meal_target(daily, _consumed_by_meal(session, user_id, date), meal)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"date": date, "meal": meal.strip().lower(), "daily_target": daily, **result}


@app.get("/users/{user_id}/progress")
def read_progress(user_id: int, date: date, session: SessionDep):
    """Target vs actual for one day, plus the weight history for the trend chart."""
    daily = _daily_targets_or_404(session, user_id)
    eaten = zero_nutrients()
    for nutrients in _consumed_by_meal(session, user_id, date).values():
        eaten = add_nutrients(eaten, nutrients)
    weights = session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date, WeightLog.id)).all()
    return {
        "date": date,
        **day_progress(daily, eaten),
        "weight_trend": [{"date": w.date, "weight_lbs": w.weight_lbs} for w in weights],
    }


# ---------- Recommendations ----------

def _placeholder_recommendation(target: dict, items: list[MenuItem]) -> dict:
    """Stand-in until D's recommend() is written: one serving of each dish in menu order until the
    calories reach the target (at most 3 dishes). Same response shape as recommend()."""
    lines, total = [], zero_nutrients()
    for item in items[:3]:
        if total["kcal"] >= target["kcal"]:
            break
        nutrients = item_nutrients(item, 1)
        lines.append({"item_id": item.id, "name": item.name, "servings": 1, **nutrients})
        total = add_nutrients(total, nutrients)
    return {"items": lines, "total": total, "target": target,
            "note": "Placeholder: not optimised yet." if lines else "No dishes on this menu fit your restrictions."}


@app.get("/recommendations/meals")
def recommend_meal(user_id: int, hall: str, date: date, meal: str, session: SessionDep):
    """
    Recommended dishes for one meal: aims at the meal's target from GET /users/{id}/meal-target,
    choosing among the dishes from GET /menu-items?user_id= (allergies and restrictions applied).
    """
    target = read_meal_target(user_id, date, meal, session)["target"]
    items = list_menu_items(hall, date, session, meal=meal, user_id=user_id)
    try:
        return recommend(target, [item.model_dump() for item in items])
    except NotImplementedError:
        return _placeholder_recommendation(target, items)
