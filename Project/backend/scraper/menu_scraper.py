"""
UIUC Dining (EatSmart / NetNutrition) menu scraper.

Walks hall -> station -> (date, meal) menu -> dishes -> nutrition label, cleans each dish,
and upserts it into the `menuitem` table.

Run from Project/backend:
    python -m scraper.menu_scraper --days 1                 # today, all halls, write to DB
    python -m scraper.menu_scraper --days 3 --halls 1 11    # next 3 days, Ike + ISR only
    python -m scraper.menu_scraper --dry-run --json out.json  # no DB write, dump JSON
"""

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://eatsmart.housing.illinois.edu/NetNutrition/46"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY = 0.2  # seconds between requests, be polite to the server

# Tags the site mixes into the allergen list that we store as flags instead
DIET_TAGS = {"vegetarian", "vegan"}

# Only these menus are recommended. Everything else (salad bar, cereal, ice cream, beverages,
# condiments, retail a la carte, ...) is still stored but flagged is_recommendable=False.
RECOMMENDABLE_MEALS = {
    "breakfast", "lunch", "light lunch", "dinner", "kosher lunch", "kosher dinner",
}


class ScrapeError(Exception):
    pass


# ---------- parsing helpers (pure functions, unit-testable) ----------

def parse_number(text: str | None) -> float | None:
    """'8g' -> 8.0, '160mg' -> 160.0, 'NA' / '' / None -> None."""
    if not text:
        return None
    m = re.match(r"\s*(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def parse_serving(raw: str | None) -> dict:
    """
    'Each (38g)'            -> size 1,   unit 'Each',  grams 38
    'Slice (1/96) (44g)'    -> size 1,   unit 'Slice (1/96)', grams 44
    '4 oz (113g)'           -> size 4,   unit 'oz',    grams 113
    """
    out = {"serving_size": None, "serving_unit": None, "serving_grams": None}
    if not raw:
        return out
    raw = raw.replace("\xa0", " ").strip()

    grams = re.search(r"\((\d+(?:\.\d+)?)\s*g\)\s*$", raw)
    if grams:
        out["serving_grams"] = float(grams.group(1))
        raw = raw[: grams.start()].strip()

    lead = re.match(r"(\d+(?:\.\d+)?)\s+(.*)", raw)
    if lead:
        out["serving_size"] = float(lead.group(1))
        out["serving_unit"] = lead.group(2).strip() or None
    else:
        out["serving_size"] = 1.0
        out["serving_unit"] = raw or None
    return out


def parse_nutrition_label(html: str) -> dict:
    """Parse one ShowItemNutritionLabel response into a flat dict (values per one serving)."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    name_td = soup.find("td", class_="cbo_nn_LabelHeader")
    result["name"] = name_td.get_text(strip=True) if name_td else None

    text = soup.get_text(" ", strip=True).replace("\xa0", " ")
    m = re.search(r"Serving Size:\s*(.+?)\s+Amount Per Serving", text)
    result.update(parse_serving(m.group(1) if m else None))

    # Rows look like: [label, value, %DV]. Only keep rows with no nested table.
    rows: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        if tr.find("tr"):
            continue
        cells = [c.get_text(" ", strip=True).replace("\xa0", " ") for c in tr.find_all("td")]
        if not cells or not cells[0]:
            continue
        if re.match(r"Calories\s+\d", cells[0]):  # "Calories 170" | "Calories from Fat 72"
            rows["Calories"] = cells[0].split(None, 1)[1]
        elif len(cells) >= 2 and cells[0] not in rows:
            rows[cells[0]] = cells[1]

    result["kcal"] = parse_number(rows.get("Calories"))
    result["protein_g"] = parse_number(rows.get("Protein"))
    result["carbs_g"] = parse_number(rows.get("Total Carbohydrate"))
    result["fat_g"] = parse_number(rows.get("Total Fat"))
    result["saturated_fat_g"] = parse_number(rows.get("Saturated Fat"))
    result["fiber_g"] = parse_number(rows.get("Dietary Fiber"))
    result["sugar_g"] = parse_number(rows.get("Sugars"))
    result["sodium_mg"] = parse_number(rows.get("Sodium"))

    ing = re.search(r"Ingredients:\s*(.*?)(?:\s*Contains:|$)", text)
    result["ingredients"] = ing.group(1).strip() if ing else None
    return result


def split_tags(tags: list[str]) -> dict:
    """Separate vegetarian/vegan flags from the real allergen names."""
    lowered = {t.strip().lower() for t in tags}
    allergens = sorted({t.strip() for t in tags if t.strip().lower() not in DIET_TAGS})
    is_vegan = "vegan" in lowered
    return {
        "allergens": allergens,
        "is_vegan": is_vegan,
        "is_vegetarian": is_vegan or "vegetarian" in lowered,
    }


def is_complete(item: dict) -> bool:
    """MVP requires kcal + the three macros."""
    return all(item.get(k) is not None for k in ("kcal", "protein_g", "carbs_g", "fat_g"))


# ---------- scraper ----------

class MenuScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._get(BASE_URL)  # sets the session cookies the API needs
        self._label_cache: dict[str, dict] = {}

    def _get(self, url):
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        return r

    def _post(self, endpoint: str, data: dict) -> dict:
        time.sleep(REQUEST_DELAY)
        r = self.session.post(f"{BASE_URL}/{endpoint}", data=data, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if not payload.get("success"):
            raise ScrapeError(f"{endpoint} {data} returned success=false")
        return payload

    @staticmethod
    def _panel(payload: dict, panel_id: str) -> str:
        for p in payload.get("panels", []):
            if p.get("id") == panel_id:
                return p.get("html", "")
        return ""

    def list_halls(self) -> dict[int, str]:
        """{unitOid: hall name} from the home page."""
        html = self._get(BASE_URL).text
        halls = re.findall(r"unitsSelectUnit\((\d+)\);\">([^<]+)</a>", html)
        return {int(oid): name.strip() for oid, name in halls}

    def list_stations(self, hall_oid: int) -> dict[int, str]:
        """{unitOid: station name} for a hall. Empty if the hall has no sub-units."""
        payload = self._post("Unit/SelectUnitFromUnitsList", {"unitOid": hall_oid})
        html = self._panel(payload, "childUnitsPanel")
        stations = re.findall(r"childUnitsSelectUnit\((\d+)\);\">([^<]+)</a>", html)
        return {int(oid): name.strip() for oid, name in stations}

    def list_menus(self, unit_oid: int, child: bool) -> list[tuple[date, str, int]]:
        """[(date, meal name, menuOid)] for a unit."""
        endpoint = "Unit/SelectUnitFromChildUnitsList" if child else "Unit/SelectUnitFromUnitsList"
        payload = self._post(endpoint, {"unitOid": unit_oid})
        html = self._panel(payload, "menuPanel")
        menus = []
        for day_text, block in re.findall(r"card-title h4'>([^<]+)</header>(.*?)</section>", html, re.S):
            try:
                day = datetime.strptime(day_text.strip(), "%A, %B %d, %Y").date()
            except ValueError:
                continue
            for menu_oid, meal in re.findall(r"menuListSelectMenu\((\d+)\);\">([^<]+)<", block):
                menus.append((day, meal.strip(), int(menu_oid)))
        return menus

    def list_dishes(self, unit_oid: int, menu_oid: int) -> list[dict]:
        payload = self._post("Menu/SelecUnitAndtMenu", {"unitOid": unit_oid, "menuOid": menu_oid})
        soup = BeautifulSoup(self._panel(payload, "itemPanel"), "html.parser")
        dishes, category = [], None
        for row in soup.find_all("tr"):
            classes = row.get("class", [])
            if "cbo_nn_itemGroupRow" in classes:
                div = row.find("div", attrs={"role": "button"})
                category = div.get_text(strip=True) if div else category
                continue
            link = row.find("a", id=re.compile(r"showNutrition_\d+"))
            btn = row.find("button", attrs={"data-detailoid": True})
            if not link or not btn:
                continue
            tags = [img.get("title") for img in link.find_all("img") if img.get("title")]
            dishes.append({
                "source_id": btn["data-detailoid"],
                "name": link.contents[0].strip() if link.contents else link.get_text(strip=True),
                "category": category,
                "tags": tags,
            })
        return dishes

    def get_label(self, detail_oid: str) -> dict:
        if detail_oid not in self._label_cache:
            time.sleep(REQUEST_DELAY)
            r = self.session.post(
                f"{BASE_URL}/NutritionDetail/ShowItemNutritionLabel",
                data={"detailOid": detail_oid}, timeout=30,
            )
            r.raise_for_status()
            if not r.text.strip():
                raise ScrapeError(f"empty nutrition label for detailOid={detail_oid}")
            self._label_cache[detail_oid] = parse_nutrition_label(r.text)
        return self._label_cache[detail_oid]

    def scrape(self, start: date, end: date, hall_oids: list[int] | None = None, log=print):
        """Yield cleaned dish dicts for menus dated start..end (inclusive). Returns via stats dict."""
        stats = {"menus": 0, "dishes": 0, "skipped_incomplete": 0, "errors": 0}
        halls = self.list_halls()
        if hall_oids:
            halls = {oid: n for oid, n in halls.items() if oid in hall_oids}

        def run():
            for hall_oid, hall_name in halls.items():
                try:
                    stations = self.list_stations(hall_oid)
                    # Halls without sub-units list their menus directly
                    targets = [(oid, name, True) for oid, name in stations.items()] or [(hall_oid, hall_name, False)]
                    for unit_oid, station_name, child in targets:
                        for day, meal, menu_oid in self.list_menus(unit_oid, child):
                            if not (start <= day <= end):
                                continue
                            stats["menus"] += 1
                            for dish in self.list_dishes(unit_oid, menu_oid):
                                try:
                                    label = self.get_label(dish["source_id"])
                                except (ScrapeError, requests.RequestException) as e:
                                    stats["errors"] += 1
                                    log(f"  ! {hall_name}/{station_name} {dish['name']}: {e}")
                                    continue
                                item = {
                                    "date": day, "hall": hall_name, "meal": meal.lower(),
                                    "station": station_name if child else None,
                                    "category": dish["category"],
                                    "source_id": dish["source_id"],
                                    **{k: v for k, v in label.items() if k != "name"},
                                    "name": dish["name"] or label.get("name"),
                                    **split_tags(dish["tags"]),
                                    "is_recommendable": meal.lower() in RECOMMENDABLE_MEALS,
                                }
                                if not is_complete(item):
                                    stats["skipped_incomplete"] += 1
                                    log(f"  - skip (missing kcal/macros): {hall_name} {dish['name']}")
                                    continue
                                stats["dishes"] += 1
                                yield item
                    log(f"✓ {hall_name}")
                except (ScrapeError, requests.RequestException) as e:
                    stats["errors"] += 1
                    log(f"✗ {hall_name}: {e}")

        return run(), stats


# ---------- database ----------

def save_items(items: list[dict]) -> tuple[int, int]:
    """Upsert into `menuitem` on (date, hall, meal, source_id). Returns (inserted, updated)."""
    from sqlmodel import Session, select

    from app.database import create_db_and_tables, engine
    from app.models import MenuItem

    create_db_and_tables()
    inserted = updated = 0
    with Session(engine) as session:
        for item in items:
            existing = session.exec(
                select(MenuItem).where(
                    MenuItem.date == item["date"], MenuItem.hall == item["hall"],
                    MenuItem.meal == item["meal"], MenuItem.source_id == item["source_id"],
                )
            ).first()
            if existing:
                for k, v in item.items():
                    setattr(existing, k, v)
                session.add(existing)
                updated += 1
            else:
                session.add(MenuItem(**item))
                inserted += 1
        session.commit()
    return inserted, updated


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=1, help="how many days from today to scrape (default 1)")
    ap.add_argument("--halls", type=int, nargs="*", help="hall unitOids (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="don't write to the database")
    ap.add_argument("--json", help="also dump the scraped items to this JSON file")
    args = ap.parse_args()

    today = date.today()
    scraper = MenuScraper()
    gen, stats = scraper.scrape(today, today + timedelta(days=args.days - 1), args.halls)
    items = list(gen)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False, default=str)
    if not args.dry_run:
        ins, upd = save_items(items)
        print(f"DB: {ins} inserted, {upd} updated")
    print(f"Done: {stats}")
    # A run that finds nothing, or hits errors, should fail loudly so the scheduled job can alert
    if not items or stats["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
