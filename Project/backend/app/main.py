from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .models import User, UserCreate, UserPublic


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: create any tables that don't exist yet
    create_db_and_tables()
    yield


app = FastAPI(title="UIUC Dining Nutrition API", lifespan=lifespan)

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
