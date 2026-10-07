import os

from sqlmodel import SQLModel, Session, create_engine

# Local development uses SQLite. In production set DATABASE_URL to the PostgreSQL URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nutrition.db")

# Some hosts (e.g. Render) hand out "postgres://" URLs, which SQLAlchemy no longer accepts,
# and we use the psycopg (v3) driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# check_same_thread is a SQLite-only option
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
