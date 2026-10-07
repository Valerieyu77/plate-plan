from datetime import date

from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Column, JSON

Date = date


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
    food_preferences: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class UserCreate(UserBase):
    pass


class UserPublic(UserBase):
    id: int


# ---------- Goal (one per user) ----------

class Goal(SQLModel, table=True):
    # user_id is the primary key, so each user can only have one goal row
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    target_weight_lbs: float | None = None
    target_date: date | None = None

    # Daily nutrition goals
    calorie_goal: int | None = None
    protein_goal_g: int | None = None
    carb_goal_g: int | None = None
    fat_goal_g: int | None = None
    sugar_limit_g: int | None = None


# ---------- Weight log ----------

class WeightLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: date
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
    meal: str = Field(index=True)  # "breakfast", "lunch", "dinner" (same values as FoodLog.meal)
    station: str | None = None  # food category on the site, e.g. "Desserts"
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
