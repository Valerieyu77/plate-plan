"""
Try recommend() on real menu data without a database.

    python -m app.try_recommend
    python -m app.try_recommend --hall "Lincoln" --meal dinner --date 2026-10-09 --kcal 700 --protein 50 --carbs 70 --fat 20
"""

import argparse
import json
from pathlib import Path

from .recommend import NUTRIENTS, recommend

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "menu_sample.json"


def load_menu(hall_part: str, date: str, meal: str) -> list[dict]:
    data = json.loads(SAMPLE.read_text())
    items = [
        i for i in data
        if hall_part.lower() in i["hall"].lower() and i["date"] == date and i["meal"] == meal
    ]
    for i in items:
        i["id"] = i.get("id") or i["source_id"]  # the sample file has no database ids
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hall", default="Illinois Street", help="part of the hall name")
    ap.add_argument("--date", default="2026-10-08")
    ap.add_argument("--meal", default="lunch")
    ap.add_argument("--kcal", type=float, default=650)
    ap.add_argument("--protein", type=float, default=45)
    ap.add_argument("--carbs", type=float, default=70)
    ap.add_argument("--fat", type=float, default=20)
    args = ap.parse_args()

    items = load_menu(args.hall, args.date, args.meal)
    target = {"kcal": args.kcal, "protein_g": args.protein, "carbs_g": args.carbs, "fat_g": args.fat}
    print(f"{len(items)} dishes on the menu ({args.hall}, {args.date}, {args.meal})")
    print("target:", target)
    if not items:
        raise SystemExit("No dishes found: check --hall / --date / --meal (dates in the sample: 2026-10-07 to 2026-10-09).")

    result = recommend(target, items)
    print()
    for line in result["items"]:
        print(f"  {line['servings']:>4} x {line['name']}  ({line['kcal']:.0f} kcal)")
    print("total: ", {k: round(result["total"][k], 1) for k in NUTRIENTS})
    print("target:", {k: round(result["target"][k], 1) for k in NUTRIENTS})
    if result.get("note"):
        print("note:  ", result["note"])


if __name__ == "__main__":
    main()
