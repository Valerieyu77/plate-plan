from datetime import date

from pydantic import field_validator, model_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Column, JSON

Date = date

ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active", "very_active"]
GOAL_TYPES = ["lose", "maintain", "gain"]


# ---------- User ----------

class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True, index=True)

    # Body info
    weight_lbs: float | None = None  # current weight; history lives in WeightLog
    height_in: float | None = None
    gender: str | None = None
    birthdate: date | None = None  # store birthdate so age is always up to date
    activity_level: str | None = None

    # Food needs and preferences (lists)
    allergies: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dietary_restrictions: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    @field_validator("activity_level")
    @classmethod
    def _check_activity_level(cls, v):
        # Stored as plain text; the allowed values are checked when the API receives them
        if v is not None and v not in ACTIVITY_LEVELS:
            raise ValueError(f"activity_level must be one of {ACTIVITY_LEVELS}")
        return v


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # bcrypt hash, never the password itself; None for accounts made before login existed
    password_hash: str | None = None


class UserCreate(UserBase):
    pass


class UserSignUp(UserCreate):
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _check_password_length(cls, v):
        # bcrypt only reads the first 72 bytes
        if len(v.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v


class UserPublic(UserBase):
    id: int


class LogIn(SQLModel):
    email: str
    password: str


class AuthResponse(SQLModel):
    token: str
    user: UserPublic


# ---------- Goal (one per user) ----------

class Goal(SQLModel, table=True):
    # user_id is the primary key, so each user can only have one goal row
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    goal_type: str | None = None  # "lose", "maintain" or "gain"
    target_weight_lbs: float | None = None

    # Timeline (all None for a plain lose / maintain / gain goal): where the user started, when they
    # want to reach target_weight_lbs, and the pace now planned (lb/week; updated on each weigh-in)
    start_date: date | None = None
    start_weight_lbs: float | None = None
    target_date: date | None = None
    weekly_rate_lbs: float | None = None

    # Daily nutrition goals
    calorie_goal: int | None = None
    protein_goal_g: int | None = None
    carb_goal_g: int | None = None
    fat_goal_g: int | None = None
    sugar_limit_g: int | None = None


class GoalCreate(SQLModel):
    """
    Either a plain goal type ({"goal_type": "lose"}: a fixed daily offset), or a timeline
    ({"target_weight_lbs": 130, "target_date": "2026-12-20"}: the pace sets the calories, and
    goal_type follows from the target).
    """
    goal_type: str | None = None
    target_weight_lbs: float | None = Field(default=None, gt=0)
    target_date: Date | None = None

    @field_validator("goal_type")
    @classmethod
    def _check_goal_type(cls, v):
        if v is not None and v not in GOAL_TYPES:
            raise ValueError(f"goal_type must be one of {GOAL_TYPES}")
        return v

    @model_validator(mode="after")
    def _goal_type_or_timeline(self):
        if (self.target_weight_lbs is None) != (self.target_date is None):
            raise ValueError("send target_weight_lbs and target_date together")
        if self.goal_type is None and self.target_date is None:
            raise ValueError("send goal_type, or target_weight_lbs and target_date")
        return self

    @property
    def has_timeline(self) -> bool:
        return self.target_date is not None


class GoalPublic(SQLModel):
    user_id: int
    goal_type: str | None = None
    target_weight_lbs: float | None = None
    start_date: Date | None = None
    start_weight_lbs: float | None = None
    target_date: Date | None = None
    weekly_rate_lbs: float | None = None
    calorie_goal: int | None = None
    protein_goal_g: int | None = None
    carb_goal_g: int | None = None
    fat_goal_g: int | None = None
    sugar_limit_g: int | None = None
    tier: str | None = None  # "healthy" or "aggressive" for a timeline goal
    warning: str | None = None  # set when the calorie target was raised to the safe minimum, or the pace is aggressive


# ---------- Weight log ----------

class WeightLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: date
    weight_lbs: float


class WeightLogCreate(SQLModel):
    weight_lbs: float = Field(gt=0)
    date: Date | None = None  # defaults to today


class WeightLogPublic(SQLModel):
    id: int
    user_id: int
    date: Date
    weight_lbs: float


# ---------- Food log ----------

class FoodLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: date
    meal: str  # e.g. "breakfast", "lunch", "dinner", "snack"
    servings: float = 1
    # Links to the dish eaten; nullable so older/manual logs still work
    item_id: int | None = Field(default=None, foreign_key="menuitem.id", index=True)


class FoodLogCreate(SQLModel):
    # The dish eaten. date and meal default to the menu item's own date and meal.
    item_id: int
    servings: float = Field(default=1, gt=0)
    date: Date | None = None
    meal: str | None = None


class FoodLogPublic(SQLModel):
    id: int
    user_id: int
    date: Date
    meal: str
    servings: float
    item_id: int | None


# ---------- Workout log ----------

class WorkoutLog(SQLModel, table=True):
    """One exercise the user did. kcal is worked out when it is logged (MET x weight x time), so a
    later change of weight doesn't rewrite old days."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: date
    exercise_id: str | None = None  # an id from app/exercises.py; None for something not in the list
    name: str
    minutes: float
    intensity: str = "moderate"
    kcal: float


class WorkoutLogCreate(SQLModel):
    """Log an exercise from the list (exercise_id), or anything else by name with your own kcal."""
    exercise_id: str | None = None
    name: str | None = None
    minutes: float = Field(gt=0, le=600)
    intensity: str = "moderate"
    kcal: float | None = Field(default=None, ge=0)  # required for an exercise not in the list
    date: Date | None = None  # defaults to today

    @model_validator(mode="after")
    def _known_exercise_or_own_numbers(self):
        if self.intensity not in ("light", "moderate", "hard"):
            raise ValueError("intensity must be light, moderate or hard")
        if self.exercise_id is None and (not self.name or self.kcal is None):
            raise ValueError("send exercise_id, or a name and kcal for an exercise not in the list")
        return self


class WorkoutLogPublic(SQLModel):
    id: int
    user_id: int
    date: Date
    exercise_id: str | None
    name: str
    minutes: float
    intensity: str
    kcal: float


# ---------- Menu item (written by the scraper, read by everyone else) ----------

class MenuItem(SQLModel, table=True):
    # One row per dish, per hall, per meal, per day.
    # source_id is the dining site's own id (detailOid), so re-running the daily scrape
    # updates rows instead of creating duplicates.
    __table_args__ = (UniqueConstraint("date", "hall", "meal", "source_id"),)

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(index=True)

    date: Date = Field(index=True)  # Date alias: a field named `date` can't be typed `date` when it has a default
    hall: str = Field(index=True)  # e.g. "Ikenberry Dining Center"
    # Menu name exactly as the dining site lists it, lowercased: "breakfast", "lunch", "dinner",
    # "light lunch", "salad bar", ... Not every hall serves every meal, so list the available
    # values per hall/date instead of hardcoding them. Do NOT merge e.g. light lunch into lunch.
    meal: str = Field(index=True)
    station: str | None = None  # sub-unit within the hall, e.g. "Baked Expectations"
    category: str | None = None  # course group on the site, e.g. "Desserts", "Entrees"
    name: str

    # One serving, e.g. 38 "g" or 1 "Each"
    serving_size: float | None = None
    serving_unit: str | None = None
    serving_grams: float | None = None  # weight of one serving in grams, when the site gives it

    # Required for the MVP; per ONE serving
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    # Stored for later, not used in calculations yet
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    saturated_fat_g: float | None = None

    # Tags. allergens use the site's names (e.g. "Milk", "Wheat") and are compared against
    # User.allergies; vegetarian/vegan are pulled out of the site's tag list.
    allergens: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_vegetarian: bool = False
    is_vegan: bool = False
    ingredients: str | None = None

    # True only for main meals (breakfast/lunch/light lunch/dinner/kosher lunch/dinner).
    # Side menus like salad bar, cereal, beverages are stored but not recommended.
    is_recommendable: bool = True


class MenuItemPublic(SQLModel):
    """What the API shows for a dish (no ingredients text or scraper ids). Nutrients are per ONE serving."""
    id: int
    date: Date
    hall: str
    meal: str
    station: str | None = None
    category: str | None = None
    name: str
    serving_size: float | None = None
    serving_unit: str | None = None
    serving_grams: float | None = None
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    allergens: list[str] = []
    is_vegetarian: bool = False
    is_vegan: bool = False
