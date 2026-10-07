"""
Copy menu items from the local SQLite file into the database named by DATABASE_URL
(e.g. the Neon PostgreSQL). Safe to run repeatedly: rows are matched on
(date, hall, meal, source_id) and updated, never duplicated.

    export DATABASE_URL='postgresql://...'      # your own terminal; never commit this
    python -m scraper.copy_menu_to_db [path/to/nutrition.db]
"""

import os
import sys

from sqlmodel import Session, create_engine, select

from app.database import DATABASE_URL, create_db_and_tables, engine
from app.models import MenuItem


def main():
    if DATABASE_URL.startswith("sqlite"):
        raise SystemExit("DATABASE_URL is not set to a PostgreSQL URL; refusing to copy SQLite onto itself.")

    source_path = sys.argv[1] if len(sys.argv) > 1 else "nutrition.db"
    if not os.path.exists(source_path):
        raise SystemExit(f"Source database not found: {source_path}")

    source = create_engine(f"sqlite:///{source_path}")
    create_db_and_tables()  # creates any missing tables in the target

    inserted = updated = 0
    with Session(source) as src, Session(engine) as dst:
        for row in src.exec(select(MenuItem)):
            data = row.model_dump(exclude={"id"})
            existing = dst.exec(
                select(MenuItem).where(
                    MenuItem.date == row.date, MenuItem.hall == row.hall,
                    MenuItem.meal == row.meal, MenuItem.source_id == row.source_id,
                )
            ).first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                dst.add(existing)
                updated += 1
            else:
                dst.add(MenuItem(**data))
                inserted += 1
        dst.commit()
    print(f"Copied menu items: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    main()
