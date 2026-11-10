import inspect
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, func, select

from .auth import CurrentUserDep, OwnerOnly, create_token, hash_password, verify_password
from .database import create_db_and_tables, get_session
from .models import (
    AccountDelete, AuthResponse, FoodLog, FoodLogCreate, FoodLogPublic, Goal, GoalCreate, GoalPublic, LogIn,
    MealsUpdate, MenuItem, PasswordChange, ProfileUpdate,
    MenuItemPublic, User, UserPublic, UserSignUp, WeightLog, WeightLogCreate, WeightLogPublic, WorkoutLog,
    WorkoutLogCreate, WorkoutLogPublic,
)
from .dietary import allowed_for_user
from .recommend import recommend, recommend_workout
from .timeline import max_safe_rate, plan_goal, replan, timeline
from .picks import high_protein_target, match_score, protein_share
from .nutrition import (
    GROUP_ORDER, MEAL_GROUP, MEAL_ORDER, NUTRIENTS, add_nutrients, daily_targets, day_progress, goal_to_targets,
    calorie_floor, exercise_in_activity, item_nutrients, meal_target, meals_in_group, missing_profile_fields, tdee,
    zero_nutrients,
)
from . import energy, events
from .exercises import BY_ID as EXERCISES_BY_ID, EXERCISES, MUSCLES, kcal_burned, video_url

log = logging.getLogger(__name__)


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

# The app is for UIUC, so "today" is Champaign's date. The server runs in UTC, where an evening in
# Illinois is already tomorrow, so date.today() would start goals and close days a day early.
try:
    CAMPUS_TZ = ZoneInfo("America/Chicago")
except ZoneInfoNotFoundError:  # no time zone data at all (the tzdata package in requirements.txt provides it)
    CAMPUS_TZ = None


def _today() -> date:
    """Today's date on campus (also usable in endpoints whose own `date` parameter hides the date class)."""
    return datetime.now(CAMPUS_TZ).date() if CAMPUS_TZ else date.today()


# How far back a forgotten meal, weigh-in or workout can still be filled in
BACKFILL_DAYS = 7


def _loggable(day: date, what: str) -> date:
    """Logs record what already happened: a date after today (on campus) is refused with 422, and so
    is one more than BACKFILL_DAYS ago. A missed day can be filled in for a week; older history
    stays as it is, so progress and the weigh-in calibration aren't rewritten long after the fact."""
    today = _today()
    if day > today:
        raise HTTPException(status_code=422, detail=f"{what} can't be logged for a future date ({day})")
    if day < today - timedelta(days=BACKFILL_DAYS):
        raise HTTPException(status_code=422,
                            detail=f"{what} can only be logged for the last {BACKFILL_DAYS} days, not {day}")
    return day


# ---------- Accounts ----------

def _user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(func.lower(User.email) == email.strip().lower())).first()


@app.post("/auth/signup", response_model=AuthResponse, status_code=201)
def sign_up(body: UserSignUp, session: SessionDep):
    """Create an account. Returns a login token and the user; 409 if the email is taken."""
    if _user_by_email(session, body.email):
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    db_user = User.model_validate(
        body.model_dump(exclude={"password"}) | {"email": body.email.strip().lower()},
        update={"password_hash": hash_password(body.password)},
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)  # loads the auto-generated id
    return AuthResponse(token=create_token(db_user.id), user=db_user)


@app.post("/auth/login", response_model=AuthResponse)
def log_in(body: LogIn, session: SessionDep):
    user = _user_by_email(session, body.email)
    # Same message whether the email or the password is wrong, so emails can't be probed
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return AuthResponse(token=create_token(user.id), user=user)


@app.get("/auth/me", response_model=UserPublic)
def read_me(user: CurrentUserDep):
    """The logged-in user, from the token; the frontend calls this to restore a session."""
    return user


@app.post("/auth/change-password", status_code=204)
def change_password(body: PasswordChange, user: CurrentUserDep, session: SessionDep):
    """Change the logged-in user's password; the current one is required. 401 if it is wrong, 422 if
    the new one is under 8 characters. The token the user has keeps working."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Your current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    session.add(user)
    session.commit()


@app.get("/users/{user_id}", response_model=UserPublic, dependencies=[OwnerOnly])
def read_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.delete("/users/{user_id}", status_code=204, dependencies=[OwnerOnly])
def delete_account(user_id: int, body: AccountDelete, session: SessionDep):
    """
    Delete the account and everything stored about it: food, weight and workout logs, the goal and
    the profile. The password is asked again. Can't be undone.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password")
    for table in (FoodLog, WeightLog, WorkoutLog):
        for row in session.exec(select(table).where(table.user_id == user_id)).all():
            session.delete(row)
    goal = session.get(Goal, user_id)
    if goal:
        session.delete(goal)
    session.flush()  # the logs and goal point at the user, so they go first
    session.delete(user)
    session.commit()


@app.patch("/users/{user_id}", response_model=UserPublic, dependencies=[OwnerOnly])
def update_profile(user_id: int, body: ProfileUpdate, session: SessionDep):
    """
    Edit the profile: name, height, sex, birthday, activity level, allergies, diet, meals. Send only
    what changes (to clear a list, send []). Allergies and diet change which dishes are shown and
    recommended right away; body and activity changes recalculate the goal's daily targets (a timeline
    goal is replanned for the time left). Weight changes go through weigh-ins.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = body.model_dump(exclude_unset=True)
    for field in ("name", "height_in", "gender", "birthdate", "activity_level"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} can't be removed, only changed")
    for key, value in changes.items():
        setattr(user, key, value)
    session.add(user)
    if changes.keys() & {"height_in", "gender", "birthdate", "activity_level"}:
        _refresh_goal(session, user)
    session.commit()
    session.refresh(user)
    return user


@app.put("/users/{user_id}/meals", response_model=UserPublic, dependencies=[OwnerOnly])
def set_meals(user_id: int, body: MealsUpdate, session: SessionDep):
    """
    Which meals the user eats each day, e.g. {"meals": ["breakfast", "dinner"]}; null for all three.
    The day's calories are then shared between those meals only, so skipping lunch makes breakfast
    and dinner bigger (meal targets, recommendations and hall picks all follow).
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.meals = body.meals
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


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


@app.post("/users/{user_id}/food-logs", response_model=FoodLogPublic, status_code=201, dependencies=[OwnerOnly])
def create_food_log(user_id: int, log: FoodLogCreate, session: SessionDep):
    """
    Log a menu dish ({"item_id", "servings"}) or quick-add anything else ({"name", "kcal"}, macros
    optional, meal default "snack", date default today): a snack, a meal off campus. Quick adds count
    everywhere a menu dish does (meal targets, progress, energy, goal progress).
    """
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if log.is_quick_add:
        db_log = FoodLog(user_id=user_id, date=_loggable(log.date or _today(), "Food"), meal=log.meal, servings=1, name=log.name,
                         kcal=log.kcal, protein_g=log.protein_g, carbs_g=log.carbs_g, fat_g=log.fat_g)
        session.add(db_log)
        session.commit()
        session.refresh(db_log)
        return db_log
    item = session.get(MenuItem, log.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db_log = FoodLog(
        user_id=user_id,
        item_id=item.id,
        servings=log.servings,
        date=_loggable(log.date or item.date, "Food"),  # e.g. a dish from tomorrow's menu
        meal=log.meal or item.meal,
    )
    session.add(db_log)
    session.commit()
    session.refresh(db_log)
    return db_log


@app.get("/users/{user_id}/food-logs", response_model=list[FoodLogPublic], dependencies=[OwnerOnly])
def list_food_logs(user_id: int, date: date, session: SessionDep):
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return session.exec(select(FoodLog).where(FoodLog.user_id == user_id, FoodLog.date == date)).all()


def _plan_or_422(user: User, goal: GoalCreate) -> dict:
    try:
        return plan_goal(user, goal.target_weight_lbs, goal.target_date, _today())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/users/{user_id}/goal/preview", dependencies=[OwnerOnly])
def preview_goal(user_id: int, goal: GoalCreate, session: SessionDep):
    """
    Check a timeline goal without saving it: the daily calories it needs, the pace, its tier
    ("healthy", "aggressive" or "unsafe"), why it is unsafe, and safe alternatives. See app/timeline.py.
    """
    if not goal.has_timeline:
        raise HTTPException(status_code=422, detail="send target_weight_lbs and target_date to preview a timeline")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _plan_or_422(user, goal)


@app.put("/users/{user_id}/goal", response_model=GoalPublic, dependencies=[OwnerOnly])
def set_goal(user_id: int, goal: GoalCreate, session: SessionDep):
    """
    Set the goal; the daily calorie and macro targets are calculated and saved. Either a goal type
    (lose / maintain / gain, fixed offset) or a target weight and date (timeline). An unsafe
    timeline is refused with 422; POST .../goal/preview shows why and what would be safe.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_goal = session.get(Goal, user_id) or Goal(user_id=user_id)
    tier = None
    if goal.has_timeline:
        plan = _plan_or_422(user, goal)
        if plan["tier"] == "unsafe":
            raise HTTPException(status_code=422, detail=" ".join(plan["issues"]))
        targets = {k: plan[k] for k in ("calorie_goal", "protein_goal_g", "carb_goal_g", "fat_goal_g", "warning")}
        tier = plan["tier"]
        timeline_fields = {
            "goal_type": plan["goal_type"], "target_weight_lbs": goal.target_weight_lbs, "target_date": goal.target_date,
            "start_date": _today(), "start_weight_lbs": user.weight_lbs, "weekly_rate_lbs": plan["weekly_rate_lbs"],
        }
        if tier == "aggressive" and not targets["warning"]:
            targets["warning"] = (f"{plan['weekly_rate_lbs']:.1f} lb a week is on the fast side. It is allowed, "
                                  "but a slower pace is easier to keep up.")
    else:
        try:
            targets = daily_targets(user, goal.goal_type, _today())
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        timeline_fields = {"goal_type": goal.goal_type, "target_weight_lbs": None, "target_date": None,
                           "start_date": None, "start_weight_lbs": None, "weekly_rate_lbs": None}

    warning = targets.pop("warning")
    for key, value in {**targets, **timeline_fields}.items():
        setattr(db_goal, key, value)
    session.add(db_goal)
    session.commit()
    session.refresh(db_goal)
    return GoalPublic(**db_goal.model_dump(), tier=tier, warning=warning)


@app.get("/users/{user_id}/goal", response_model=GoalPublic, dependencies=[OwnerOnly])
def read_goal(user_id: int, session: SessionDep):
    goal = session.get(Goal, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="No goal set for this user")
    return goal


@app.get("/users/{user_id}/goal/timeline", dependencies=[OwnerOnly])
def read_goal_timeline(user_id: int, session: SessionDep):
    """Planned weight week by week next to the logged weigh-ins, whether the user is on track, and
    when they should reach the target at the current pace. 404 without a timeline goal."""
    goal = session.get(Goal, user_id)
    if not goal or not goal.target_date:
        raise HTTPException(status_code=404, detail="No timeline goal set for this user")
    weights = session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date, WeightLog.id)).all()
    return timeline(goal, weights, _today())


# ---------- Menus ----------

@app.get("/halls", response_model=list[str])
def list_halls(session: SessionDep, date: date | None = None, meal: str | None = None):
    """Halls that have menu data (on `date`, if given), for the hall dropdown.

    With `meal` ("breakfast", "lunch" or "dinner"), only halls that serve that meal on that date.
    "lunch" also counts "light lunch" and "kosher lunch"; a raw name like "light lunch" matches only itself.

    Order: the big dining centers (Ike, ISR, LAR, PAR), then other halls with main meals
    (Everybody Eats, Kosher Kitchen), then retail shops (57 North, Caffeinator, ...), so the
    first hall is a sensible default.
    """
    query = select(MenuItem.hall, MenuItem.is_recommendable).distinct()
    if date:
        query = query.where(MenuItem.date == date)
    if meal:
        query = query.where(MenuItem.meal.in_(meals_in_group(meal)), MenuItem.is_recommendable)
    rows = session.exec(query).all()
    halls = {hall for hall, _ in rows}
    with_main_meals = {hall for hall, recommendable in rows if recommendable}

    def rank(hall):
        if hall not in with_main_meals:
            return 2
        return 0 if "Dining" in hall else 1

    return sorted(halls, key=lambda h: (rank(h), h))


@app.get("/meal-options")
def meal_options(hall: str, date: date, session: SessionDep):
    """
    The meals a hall serves on a date, grouped the way people think of them, for the meal picker:
    {"breakfast": ["breakfast"], "lunch": ["light lunch", "lunch"], "dinner": ["dinner"]}.
    A group is left out if the hall doesn't serve it; a group with more than one entry means the
    user should be asked which one (e.g. "light lunch" or "lunch"). Side menus are not included.
    """
    names = session.exec(
        select(MenuItem.meal).where(MenuItem.hall == hall, MenuItem.date == date, MenuItem.is_recommendable).distinct()
    ).all()
    options: dict[str, list[str]] = {}
    for group in GROUP_ORDER:
        in_group = sorted((m for m in names if MEAL_GROUP.get(m) == group), key=MEAL_ORDER.index)
        if in_group:
            options[group] = in_group
    return options


@app.get("/menu-items", response_model=list[MenuItemPublic], dependencies=[OwnerOnly])
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

@app.delete("/users/{user_id}/food-logs/{log_id}", status_code=204, dependencies=[OwnerOnly])
def delete_food_log(user_id: int, log_id: int, session: SessionDep):
    log = session.get(FoodLog, log_id)
    if not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="Food log not found")
    session.delete(log)
    session.commit()


# ---------- Weight logs ----------

@app.post("/users/{user_id}/weight-logs", response_model=WeightLogPublic, status_code=201, dependencies=[OwnerOnly])
def create_weight_log(user_id: int, entry: WeightLogCreate, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    day = _loggable(entry.date or _today(), "A weigh-in")
    log = WeightLog(user_id=user_id, date=day, weight_lbs=entry.weight_lbs)
    session.add(log)

    # The user's current weight (used for targets) follows the most recent weigh-in
    latest = session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date.desc())).first()
    if latest is None or day >= latest.date:
        user.weight_lbs = entry.weight_lbs
        session.add(user)
        # A timeline goal's calories follow what is left to lose or gain in the time left
        goal = session.get(Goal, user_id)
        if goal and goal.target_date and goal.goal_type:
            targets = replan(user, goal.goal_type, goal.target_weight_lbs, goal.target_date, _today())
            targets.pop("warning")
            for key, value in targets.items():
                setattr(goal, key, value)
            session.add(goal)
    session.commit()
    session.refresh(log)
    return log


@app.delete("/users/{user_id}/weight-logs/{log_id}", status_code=204, dependencies=[OwnerOnly])
def delete_weight_log(user_id: int, log_id: int, session: SessionDep):
    """
    Remove a weigh-in (a typo, say). The user's current weight goes back to the latest weigh-in that
    is left (or the goal's start weight when none is left), and a timeline goal is replanned from it,
    the same way a new weigh-in replans it.
    """
    user = session.get(User, user_id)
    log = session.get(WeightLog, log_id)
    if not user or not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="Weight log not found")
    session.delete(log)
    session.flush()
    latest = session.exec(select(WeightLog).where(WeightLog.user_id == user_id)
                          .order_by(WeightLog.date.desc(), WeightLog.id.desc())).first()
    goal = session.get(Goal, user_id)
    fallback = goal.start_weight_lbs if goal and goal.start_weight_lbs else user.weight_lbs
    user.weight_lbs = latest.weight_lbs if latest else fallback
    session.add(user)
    _refresh_goal(session, user, timeline_only=True)
    session.commit()


def _refresh_goal(session: Session, user: User, timeline_only: bool = False) -> None:
    """Recalculate the saved goal's daily targets after the profile or weight changed: a timeline goal
    is replanned for what is left by its date; a plain goal (unless timeline_only) gets the same
    goal type's targets for the new profile. Nothing to do without a goal or with an incomplete profile."""
    goal = session.get(Goal, user.id)
    if not goal or not goal.goal_type or missing_profile_fields(user):
        return
    if goal.target_date:
        targets = replan(user, goal.goal_type, goal.target_weight_lbs, goal.target_date, _today())
    elif timeline_only:
        return
    else:
        targets = daily_targets(user, goal.goal_type, _today())
    targets.pop("warning", None)
    for key, value in targets.items():
        if hasattr(goal, key):
            setattr(goal, key, value)
    session.add(goal)


@app.get("/users/{user_id}/weight-logs", response_model=list[WeightLogPublic], dependencies=[OwnerOnly])
def list_weight_logs(user_id: int, session: SessionDep):
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date, WeightLog.id)).all()


# ---------- Targets and progress ----------

def _food_logs_with_items(session: Session, user_id: int, start: date, end: date):
    """(log, menu item or None) for the user's food logs from start to end inclusive."""
    return session.exec(
        select(FoodLog, MenuItem)
        .join(MenuItem, MenuItem.id == FoodLog.item_id, isouter=True)
        .where(FoodLog.user_id == user_id, FoodLog.date >= start, FoodLog.date <= end)
    ).all()


def _log_nutrients(log: FoodLog, item: MenuItem | None) -> dict:
    """What a food log adds up to: a menu dish times its servings, or a quick add's own numbers
    (macros left out count as 0). A log with neither (very old data) counts as nothing."""
    if item is not None:
        return item_nutrients(item, log.servings)
    if log.kcal is not None:
        return item_nutrients(log, 1)
    return zero_nutrients()


def _consumed_by_meal(session: Session, user_id: int, day: date) -> dict[str, dict]:
    """{meal: nutrients eaten} from the user's food logs for a day, menu dishes and quick adds alike.
    A snack is its own "meal": it comes off the day without taking a breakfast, lunch or dinner slot."""
    by_meal: dict[str, dict] = {}
    for log, item in _food_logs_with_items(session, user_id, day, day):
        total = by_meal.setdefault(log.meal, zero_nutrients())
        by_meal[log.meal] = add_nutrients(total, _log_nutrients(log, item))
    return by_meal


def _daily_targets_or_404(session: Session, user_id: int) -> dict:
    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    goal = session.get(Goal, user_id)
    if not goal or not goal.calorie_goal:
        raise HTTPException(status_code=404, detail="No goal set for this user; call PUT /users/{id}/goal first")
    return goal_to_targets(goal)


@app.get("/users/{user_id}/meal-target", dependencies=[OwnerOnly])
def read_meal_target(user_id: int, date: date, meal: str, session: SessionDep):
    """
    What is left to eat at this meal: the day's target minus what was logged at earlier meals,
    shared between this meal and the ones after it, minus what is already logged at this meal.
    This is what the recommendation step is asked to hit.
    """
    daily = _daily_targets_or_404(session, user_id)
    try:
        result = meal_target(daily, _consumed_by_meal(session, user_id, date), meal, session.get(User, user_id).meals)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"date": date, "meal": meal.strip().lower(), "daily_target": daily,
            "meals_eaten": session.get(User, user_id).meals or list(GROUP_ORDER), **result}


@app.get("/users/{user_id}/progress", dependencies=[OwnerOnly])
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

# At most this many servings of one dish on a recommended plate: "3 servings of salad" (4.5 cups) is
# not a meal anyone takes, so a bigger budget is filled with more dishes instead. Checked on the sample
# menus for 1,000-1,250 kcal plates (someone who eats twice a day): with 2, calories still land within
# 10% on 34-35 of 37 menus with about 4 dishes; 3 hit protein a little more often but put a dish at 3
# servings on most plates.
MAX_SERVINGS_PER_DISH = 2.0


def _servings_cap(target: dict) -> float:
    return MAX_SERVINGS_PER_DISH

def _placeholder_recommendation(target: dict, items: list[MenuItem], note: str = "Placeholder: not optimised yet.") -> dict:
    """Stand-in used when recommend() is missing or fails: one serving of each real dish (skipping
    herbs and sauces under 40 kcal) in menu order until the calories reach the target, at most 3 dishes.
    Same response shape as recommend()."""
    lines, total = [], zero_nutrients()
    for item in [i for i in items if i.kcal >= 40][:3]:
        if total["kcal"] >= target["kcal"]:
            break
        nutrients = item_nutrients(item, 1)
        lines.append({"item_id": item.id, "name": item.name, "servings": 1, **nutrients})
        total = add_nutrients(total, nutrients)
    return {"items": lines, "total": total, "target": target,
            "note": note if lines else "No dishes on this menu fit your restrictions."}


def _is_valid_recommendation(result) -> bool:
    """Guard against a broken recommend(): the shape the frontend relies on must be there."""
    try:
        if not isinstance(result, dict) or not isinstance(result["items"], list):
            return False
        for block in (result["total"], result["target"]):
            if not all(isinstance(block[k], (int, float)) for k in NUTRIENTS):
                return False
        for line in result["items"]:
            if not all(k in line for k in ("item_id", "name", "servings", *NUTRIENTS)):
                return False
            if not isinstance(line["servings"], (int, float)) or line["servings"] <= 0:
                return False
        return "note" in result
    except (KeyError, TypeError):
        return False


@app.get("/recommendations/meals", dependencies=[OwnerOnly])
def recommend_meal(user_id: int, hall: str, date: date, meal: str, session: SessionDep, avoid: str | None = None):
    """
    Recommended dishes for one meal: aims at the meal's target from GET /users/{id}/meal-target,
    choosing among the dishes from GET /menu-items?user_id= (allergies and restrictions applied).
    `avoid` is a comma-separated list of item ids to steer away from; send the ids of the tray the user
    is looking at to get a different, similarly good one ("show me another"). Without it the answer is
    always the same. If recommend() is missing, errors, or returns something malformed, a simple
    placeholder in the same shape is returned instead, so the page never breaks.
    """
    target = read_meal_target(user_id, date, meal, session)["target"]
    items = list_menu_items(hall, date, session, meal=meal, user_id=user_id)
    avoid_ids = [int(x) for x in (avoid or "").split(",") if x.strip().isdigit()]
    kwargs = {"avoid_ids": avoid_ids} if avoid_ids and "avoid_ids" in inspect.signature(recommend).parameters else {}
    try:
        result = recommend(target, [item.model_dump() for item in items], max_servings=_servings_cap(target), **kwargs)
    except NotImplementedError:
        return _placeholder_recommendation(target, items)
    except Exception:
        log.exception("recommend() failed")
        return _placeholder_recommendation(target, items, "Recommendation engine unavailable; showing a simple placeholder.")
    if not _is_valid_recommendation(result):
        log.error("recommend() returned a malformed result: %r", result)
        return _placeholder_recommendation(target, items, "Recommendation engine unavailable; showing a simple placeholder.")
    return result


# ---------- Today's best picks across halls ----------

def _default_option(options: list[str]) -> str:
    """When a hall has several menus for a meal (light lunch, lunch), compare on the plain one."""
    return "lunch" if "lunch" in options else options[0]


@app.get("/users/{user_id}/hall-picks", dependencies=[OwnerOnly])
def hall_picks(user_id: int, date: date, meal: str, session: SessionDep):
    """
    Which hall suits the user best for a meal ("breakfast", "lunch" or "dinner"): at every hall that
    serves it, build the best plate for what the user still needs at that meal and say how well it
    matches (0-100), plus a high-protein plate that stays inside the same calories. Halls are sorted
    by match. Allergies and diet are respected; halls where nothing is left to eat are left out.
    """
    group = meal.strip().lower()
    if group not in GROUP_ORDER:
        raise HTTPException(status_code=422, detail=f"meal must be one of {GROUP_ORDER}")
    target = read_meal_target(user_id, date, group, session)["target"]

    results = []
    for hall in list_halls(session, date=date, meal=group):
        options = meal_options(hall, date, session).get(group)
        if not options:
            continue
        chosen = _default_option(options)
        items = list_menu_items(hall, date, session, meal=chosen, user_id=user_id)
        dishes = [item.model_dump() for item in items]
        try:
            tray = recommend(target, dishes, max_servings=_servings_cap(target))
            protein_plate = recommend(high_protein_target(target["kcal"]), dishes, max_servings=_servings_cap(target))
        except Exception:
            log.exception("hall-picks: recommend() failed for %s", hall)
            continue
        if not tray.get("items"):
            continue
        results.append({
            "hall": hall,
            "meal": chosen,
            "match": match_score(target, tray["total"]),
            "tray": {"items": tray["items"], "total": tray["total"], "note": tray["note"]},
            "high_protein": {
                "items": protein_plate["items"], "total": protein_plate["total"],
                "protein_share": protein_share(protein_plate["total"]), "note": protein_plate["note"],
            },
        })
    results.sort(key=lambda r: (-r["match"], r["hall"]))
    # Only a hall that really has a high-protein plate can be named: never an empty one
    best_protein = max((r for r in results if r["high_protein"]["items"]), key=lambda r: r["high_protein"]["total"]["protein_g"], default=None)
    return {
        "date": date, "meal": group, "target": target, "halls": results,
        "best_match": results[0]["hall"] if results else None,
        "best_protein": best_protein["hall"] if best_protein else None,
    }


# ---------- Exercises and workout plans ----------

def _user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _exercise_public(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("dose", "max_minutes")} | {"video_url": video_url(e)}


@app.get("/exercises")
def list_exercises(kind: str | None = None, muscle: str | None = None, equipment: str | None = None):
    """The exercise list (app/exercises.py), optionally only one kind ("cardio", "strength",
    "mobility"), one muscle group, or equipment whose name contains `equipment`."""
    out = [e for e in EXERCISES
           if (not kind or e["kind"] == kind)
           and (not muscle or muscle in e["muscles"])
           and (not equipment or equipment.lower() in e["equipment"].lower())]
    return [_exercise_public(e) for e in out]


def _kcal_eaten(session: Session, user_id: int, day: date) -> float:
    return sum(n["kcal"] for n in _consumed_by_meal(session, user_id, day).values())


@app.get("/users/{user_id}/workout", dependencies=[OwnerOnly])
def recommend_user_workout(user_id: int, session: SessionDep, date: date | None = None, intensity: str | None = None,
                           minutes: int | None = None, focus: str | None = None, muscles: str | None = None,
                           no_equipment: bool = False, avoid: str | None = None):
    """
    A workout for the day. Everything is optional: with nothing set, the goal picks the focus
    (lose: cardio, maintain: mixed, gain: strength) at moderate intensity for 35 minutes.
    muscles: comma-separated groups to train (legs, glutes, chest, back, shoulders, arms, core, heart).
    avoid: comma-separated exercise ids already shown, for "show me another".
    The same day gives the same plan; each exercise says what equipment to use, for how long,
    how to do it (with a video search link), and roughly what it burns.
    """
    user = _user_or_404(session, user_id)
    day = date or _today()
    goal = session.get(Goal, user_id)
    calorie_goal = goal.calorie_goal if goal and goal.calorie_goal else 0
    eaten = _kcal_eaten(session, user_id, day)
    try:
        plan = recommend_workout(
            goal.goal_type if goal else "maintain", calorie_goal, eaten if calorie_goal else 0,
            intensity=intensity, minutes=minutes, focus=focus,
            muscles=[m.strip().lower() for m in muscles.split(",") if m.strip()] if muscles else None,
            weight_lbs=user.weight_lbs, no_equipment=no_equipment,
            avoid=[a.strip() for a in (avoid or "").split(",") if a.strip()], seed=f"{user_id}|{day}",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"date": day, **plan}


# ---------- Workout logs ----------

@app.post("/users/{user_id}/workout-logs", response_model=WorkoutLogPublic, status_code=201, dependencies=[OwnerOnly])
def create_workout_log(user_id: int, entry: WorkoutLogCreate, session: SessionDep):
    """Log an exercise. From the list, kcal is estimated from its MET, your weight and the minutes
    (send kcal to use your own number, e.g. from a watch)."""
    user = _user_or_404(session, user_id)
    if entry.exercise_id is not None:
        exercise = EXERCISES_BY_ID.get(entry.exercise_id)
        if not exercise:
            raise HTTPException(status_code=422, detail=f"unknown exercise_id '{entry.exercise_id}'; see GET /exercises")
        name = entry.name or exercise["name"]
        kcal = entry.kcal
        if kcal is None:
            if not user.weight_lbs:
                raise HTTPException(status_code=422, detail="add your weight to your profile, or send kcal")
            kcal = kcal_burned(exercise["met"][entry.intensity], user.weight_lbs, entry.minutes)
    else:
        name, kcal = entry.name, entry.kcal
    log = WorkoutLog(user_id=user_id, date=_loggable(entry.date or _today(), "A workout"), exercise_id=entry.exercise_id,
                     name=name, minutes=entry.minutes, intensity=entry.intensity, kcal=round(kcal, 1))
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@app.get("/users/{user_id}/workout-logs", response_model=list[WorkoutLogPublic], dependencies=[OwnerOnly])
def list_workout_logs(user_id: int, session: SessionDep, date: date | None = None):
    _user_or_404(session, user_id)
    query = select(WorkoutLog).where(WorkoutLog.user_id == user_id)
    if date:
        query = query.where(WorkoutLog.date == date)
    return session.exec(query.order_by(WorkoutLog.date, WorkoutLog.id)).all()


@app.delete("/users/{user_id}/workout-logs/{log_id}", status_code=204, dependencies=[OwnerOnly])
def delete_workout_log(user_id: int, log_id: int, session: SessionDep):
    log = session.get(WorkoutLog, log_id)
    if not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="Workout log not found")
    session.delete(log)
    session.commit()


# ---------- Energy balance and progress toward the goal ----------

def _ledger_days(session: Session, user_id: int, start: date, end: date) -> dict:
    """{day: {"eaten": kcal or None, "exercise": kcal}} for start..end inclusive. eaten is None on
    a day with no food logged (unknown, not zero)."""
    days = {}
    for log, item in _food_logs_with_items(session, user_id, start, end):
        d = days.setdefault(log.date, {"eaten": 0.0, "exercise": 0.0})
        d["eaten"] += _log_nutrients(log, item)["kcal"]
    for w in session.exec(select(WorkoutLog).where(WorkoutLog.user_id == user_id, WorkoutLog.date >= start,
                                                   WorkoutLog.date <= end)).all():
        days.setdefault(w.date, {"eaten": None, "exercise": 0.0})["exercise"] += w.kcal
    return days


def _energy_context(session: Session, user_id: int, today: date):
    """The user, their goal, the logged days, their weigh-ins and the calibrated daily burn."""
    user = _user_or_404(session, user_id)
    goal = session.get(Goal, user_id)
    if not goal or not goal.calorie_goal:
        raise HTTPException(status_code=404, detail="No goal set for this user; call PUT /users/{id}/goal first")
    missing = missing_profile_fields(user)
    if missing:
        raise HTTPException(status_code=422, detail=f"profile is missing: {', '.join(missing)}")
    start = min(goal.start_date or today, today - timedelta(days=energy.CALIBRATION_WINDOW))
    days = energy.count_workouts(_ledger_days(session, user_id, start, today), exercise_in_activity(user, today))
    weights = session.exec(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.date, WeightLog.id)).all()
    formula = tdee(user, today)
    calibration = energy.calibrate(days, [w for w in weights if w.date <= today], formula, today)
    return user, goal, days, weights, formula * calibration["factor"], calibration


@app.get("/users/{user_id}/energy", dependencies=[OwnerOnly])
def read_energy(user_id: int, date: date, session: SessionDep):
    """
    One day's calories in and out: eaten, the daily burn (adjusted to the user's weigh-ins once there
    is enough data), workouts, the net, and how the day compares with the plan (status "ahead",
    "on_track", "behind", or "over"/"under" for maintain; "not_logged" with no food logged;
    "too_low" for a past day under the safe calorie minimum). Today isn't over, so its status is
    "in_progress" (the numbers are what was logged so far) and day_complete is false.
    Workouts: exercise_logged is everything logged; exercise is the part beyond the average day's
    exercise the activity level already includes (exercise_in_activity), so nothing counts twice.
    """
    user, goal, days, _, burn, calibration = _energy_context(session, user_id, date)
    d = days.get(date, {"eaten": None, "exercise": 0.0, "exercise_logged": 0.0})
    workouts = session.exec(select(WorkoutLog).where(WorkoutLog.user_id == user_id, WorkoutLog.date == date)
                            .order_by(WorkoutLog.id)).all()
    complete = date < _today()
    # Today isn't over, so only a past day can count as under the minimum
    balance = energy.day_balance(goal.goal_type, goal.calorie_goal, burn, d["eaten"], d["exercise"],
                                 calorie_floor(user) if complete else None)
    if not complete and balance["status"] != "not_logged":
        # A half-logged day would read as "ahead" every evening; say it is still going instead
        balance["status"] = "in_progress"
    return {
        "date": date,
        "goal_type": goal.goal_type,
        "calorie_goal": goal.calorie_goal,
        **balance,
        # exercise (above) is what counts on top of the daily burn; the rest of what was logged is
        # already part of the activity level picked at sign-up
        "exercise_logged": round(d["exercise_logged"]),
        "exercise_in_activity": round(exercise_in_activity(user, date)),
        "day_complete": complete,
        "workouts": [WorkoutLogPublic.model_validate(w) for w in workouts],
        "burn_adjusted": calibration["factor"] != 1.0,
    }


@app.get("/users/{user_id}/goal/progress", dependencies=[OwnerOnly])
def read_goal_progress(user_id: int, session: SessionDep, date: date | None = None):
    """
    How the logged days add up: kcal (and lb) ahead of or behind the plan, and for a timeline goal
    how many days earlier or later it should finish. Also the weight the logs suggest today (the
    latest smoothed weigh-in plus calories since), the scale-based status from the timeline, and
    how the daily burn has been adjusted to the user's weigh-ins. For a timeline goal the logs count
    from the latest weigh-in, which replanned the calories; a pace that isn't safe is "unsafe_pace".
    """
    today = date or _today()
    user, goal, days, weights, burn, calibration = _energy_context(session, user_id, today)
    weights_so_far = [w for w in weights if w.date <= today]
    max_rate = max_safe_rate(user, goal.goal_type, today) if goal.goal_type in ("lose", "gain") else None
    progress = energy.goal_progress(goal, days, burn, today, weights_so_far, calorie_floor(user), max_rate)
    estimate = energy.estimate_weight(weights_so_far, days, burn, goal.start_weight_lbs or user.weight_lbs,
                                      goal.start_date or today, today)
    scale = None
    if goal.target_date:
        t = timeline(goal, weights_so_far, today)
        scale = {k: t[k] for k in ("status", "latest_weight_lbs", "expected_weight_lbs", "remaining_lbs",
                                   "projected_finish_date")}
    return {
        "goal_type": goal.goal_type,
        "target_date": goal.target_date,
        **progress,
        "message": energy.progress_message(progress, goal.goal_type,
                                           today_logged=(days.get(today) or {}).get("eaten") is not None),
        "weight": estimate,
        "scale": scale,
        "calibration": calibration,
    }


# ---------- Campus fitness events ----------

@app.get("/events")
def list_events(start: date | None = None, days: int = 7, fitness_only: bool = True, q: str | None = None):
    """
    Upcoming events from the campus "Recreation, Health & Wellness" calendar: by default the
    exercise ones (skating, classes, runs, ...) in the next 7 days. fitness_only=false includes
    wellness events too; q searches the title, place and description.
    """
    if not 1 <= days <= 31:
        raise HTTPException(status_code=422, detail="days must be between 1 and 31")
    try:
        all_events = events.fetch_events()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Couldn't reach the campus calendar; try again in a minute")
    start = start or _today()
    found = events.upcoming(all_events, start, days, fitness_only, q)
    return {"start": start, "days": days, "source": events.CALENDAR_PAGE, "events": found}
