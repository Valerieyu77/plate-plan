from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .models import (
    FoodLog, FoodLogCreate, FoodLogPublic, Goal, GoalCreate, GoalPublic, MenuItem, User, UserCreate, UserPublic,
)
from .nutrition import daily_targets


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
