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
        rows = src.exec(select(MenuItem)).all()
        print(f"Read {len(rows)} rows from {source_path}; loading what the target already has...")

        # One query for everything already in the target, instead of one per row (much faster over the network)
        key = lambda m: (m.date, m.hall, m.meal, m.source_id)
        existing = {key(m): m for m in dst.exec(select(MenuItem)).all()}

        for row in rows:
            data = row.model_dump(exclude={"id"})
            current = existing.get(key(row))
            if current:
                for k, v in data.items():
                    setattr(current, k, v)
                updated += 1
            else:
                dst.add(MenuItem(**data))
                inserted += 1
        print("Writing to the target database...")
        dst.commit()
    print(f"Copied menu items: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    main()
