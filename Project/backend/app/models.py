from sqlmodel import SQLModel, Field, Column, JSON


class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True, index=True)

    # Body info
    weight_lbs: float | None = None
    target_weight_lbs: float | None = None
    height_in: float | None = None

    # Daily nutrition goals
    calorie_goal: int | None = None
    protein_goal_g: int | None = None
    carb_goal_g: int | None = None
    fat_goal_g: int | None = None
    sugar_limit_g: int | None = None

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