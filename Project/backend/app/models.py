from datetime import date

from sqlmodel import SQLModel, Field, Column, JSON


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
    # TODO: add item_id once the dining hall food database is ready
    date: date
    meal: str  # e.g. "breakfast", "lunch", "dinner", "snack"
    servings: float = 1
