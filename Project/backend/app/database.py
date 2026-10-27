import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine

# Pick up DATABASE_URL from Project/backend/.env if it exists (gitignored; never commit it).
# A DATABASE_URL already set in the terminal wins over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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


def create_db_and_tables(bind=None):
    bind = bind or engine
    SQLModel.metadata.create_all(bind)
    add_missing_columns(bind)


def add_missing_columns(bind):
    """
    create_all makes missing tables but never changes a table that already exists, so a column added
    to a model later (e.g. User.password_hash) would be missing from the live database. This adds
    such columns. Only nullable columns are added (no defaults to fill in), so existing rows stay
    valid; anything more involved needs a real migration.
    """
    existing_tables = set(inspect(bind).get_table_names())
    with bind.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspect(conn).get_columns(table.name)}
            for column in table.columns:
                if column.name in have or not column.nullable:
                    continue
                col_type = column.type.compile(dialect=conn.dialect)
                prep = conn.dialect.identifier_preparer
                conn.execute(text(f"ALTER TABLE {prep.quote(table.name)} ADD COLUMN {prep.quote(column.name)} {col_type}"))


def get_session():
    with Session(engine) as session:
        yield session
