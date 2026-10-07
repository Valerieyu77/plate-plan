"""
UIUC Dining EatSmart Scraper - Proof of Concept
Fetches menu items and nutrition details using the discovered internal API.

API Flow:
1. POST /Menu/SelecUnitAndtMenu with {unitOid, menuOid} -> returns menu HTML (item list + detailOid for each item)
2. Parse HTML to extract each item's name, detailOid, serving size, allergen tags
3. POST /NutritionDetail/ShowItemNutritionLabel with {detailOid} -> returns nutrition label HTML
4. Parse nutrition HTML to extract calories, macros, allergens, ingredients
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time

BASE_URL = "https://eatsmart.housing.illinois.edu/NetNutrition/46"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}


class DiningScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Visiting the main page first sets session cookies required by the API
        self.session.get(f"{BASE_URL}")

    def get_menu_items(self, unit_oid: int, menu_oid: int):
        """
        Step 1: Fetch the menu item list for a given unit + menu combination.
        Returns a list of dicts: [{name, detail_oid, serving_size, allergens}, ...]
        """
        url = f"{BASE_URL}/Menu/SelecUnitAndtMenu"
        payload = {"unitOid": unit_oid, "menuOid": menu_oid}

        response = self.session.post(url, data=payload)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            print(f"  ✗ API returned success=false for unitOid={unit_oid}, menuOid={menu_oid}")
            return []

        # Find the "itemPanel" which contains the menu item HTML
        item_html = ""
        for panel in data.get("panels", []):
            if panel.get("id") == "itemPanel":
                item_html = panel.get("html", "")
                break

        if not item_html:
            print(f"  ✗ No itemPanel found for unitOid={unit_oid}, menuOid={menu_oid}")
            return []

        return self._parse_menu_html(item_html)

    def _parse_menu_html(self, html: str):
        """Parse the itemPanel HTML to extract menu items."""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # Each menu item row has class 'cbo_nn_itemPrimaryRow' or 'cbo_nn_itemAlternateRow'
        rows = soup.find_all("tr", class_=re.compile(r"cbo_nn_item(Primary|Alternate)Row"))

        # Also track current category (Desserts, Entrees, etc.) from the group header rows
        all_rows = soup.find_all("tr")
        current_category = None

        for row in all_rows:
            # Category header row
            if "cbo_nn_itemGroupRow" in row.get("class", []):
                div = row.find("div", attrs={"role": "button"})
                if div:
                    current_category = div.get_text(strip=True)
                continue

            # Menu item row
            classes = row.get("class", [])
            if any("cbo_nn_item" in c and "Row" in c and "Group" not in c for c in classes):
                # Find the detailOid from the "add item" button
                add_btn = row.find("button", attrs={"data-detailoid": True})
                detail_oid = add_btn["data-detailoid"] if add_btn else None

                # Find the item name link
                name_link = row.find("a", id=re.compile(r"showNutrition_\d+"))
                if not name_link:
                    continue

                # The name is the link's text, but it also contains allergen <img> tags
                # Extract just the text node (the dish name) before the <span> tags
                name = name_link.contents[0].strip() if name_link.contents else name_link.get_text(strip=True)

                # Extract allergen tags from <img title='...'> inside the link
                allergens = [img.get("title") for img in name_link.find_all("img") if img.get("title")]

                # Serving size is in the next <td>
                tds = row.find_all("td")
                serving_size = tds[2].get_text(strip=True) if len(tds) > 2 else None

                items.append({
                    "name": name,
                    "detail_oid": detail_oid,
                    "category": current_category,
                    "serving_size": serving_size,
                    "allergens": allergens,
                })

        return items

    def get_nutrition_detail(self, detail_oid: str):
        """
        Step 2: Fetch full nutrition info for a single item by its detailOid.
        Returns a dict of parsed nutrition fields.
        """
        url = f"{BASE_URL}/NutritionDetail/ShowItemNutritionLabel"
        payload = {"detailOid": detail_oid}

        response = self.session.post(url, data=payload)
        response.raise_for_status()

        return self._parse_nutrition_html(response.text)

    def _parse_nutrition_html(self, html: str):
        """Parse the nutrition label HTML into structured fields."""
        soup = BeautifulSoup(html, "html.parser")
        result = {}

        # Dish name
        name_td = soup.find("td", class_="cbo_nn_LabelHeader")
        result["name"] = name_td.get_text(strip=True) if name_td else None

        # Serving size (e.g. "Serving Size: Each (38g)")
        serving_td = soup.find("td", class_="cbo_nn_LabelBottomBorderLabel")
        if serving_td:
            text = serving_td.get_text(" ", strip=True)
            match = re.search(r"Serving Size:\s*(.+)", text)
            result["serving_size_raw"] = match.group(1) if match else text

        # Helper to find a nutrient value by its bold label text
        def find_nutrient(label_text):
            label_span = soup.find("span", string=lambda s: s and s.strip() == label_text)
            if not label_span:
                return None
            # The value is usually in a sibling <span class="cbo_nn_SecondaryNutrient">
            parent_td = label_span.find_parent("td")
            if not parent_td:
                return None
            value_span = parent_td.find("span", class_="cbo_nn_SecondaryNutrient")
            return value_span.get_text(strip=True) if value_span else None

        # Calories
        result["kcal"] = find_nutrient("Calories")

        # Every nutrient row (Total Fat, Saturated Fat, Sodium, Dietary Fiber, Sugars, etc.)
        # lives in a <td class="cbo_nn_LabelDetail"> (bold, top-level) or
        # <td class="cbo_nn_Nutrient"> / indented rows (sub-items like Saturated Fat).
        # The label text itself is in a <span>, and the value follows in another <span>
        # with class 'cbo_nn_SecondaryNutrient' OR as plain text in the same <td>.
        nutrient_map = {}
        label_classes = ["cbo_nn_LabelDetail", "cbo_nn_Nutrient"]
        for td in soup.find_all("td", class_=lambda c: c and any(lc in c for lc in label_classes)):
            label_span = td.find("span")
            if not label_span:
                continue
            label = label_span.get_text(strip=True)
            if not label or label in nutrient_map:
                continue

            # Value is in the next <td> (right-aligned column), possibly nested in a span
            next_td = td.find_next_sibling("td")
            if next_td:
                value = next_td.get_text(strip=True)
                # Strip trailing % daily value if present (e.g. "8g12%" -> keep as-is, flag separately)
                nutrient_map[label] = value

        result["raw_nutrients"] = nutrient_map

        # Calories from Fat (special case: appears inline in the same td as Calories)
        cff_match = re.search(r"Calories from Fat\s*(\d+)", soup.get_text(" ", strip=True))
        if cff_match:
            result["calories_from_fat"] = cff_match.group(1)

        # Ingredients
        page_text = soup.get_text("\n", strip=True)
        ing_match = re.search(r"Ingredients:(.*?)(?:Contains:|$)", page_text, re.DOTALL)
        result["ingredients"] = ing_match.group(1).strip() if ing_match else None

        # Contains / allergens -- search raw HTML text (not just get_text) since
        # "Contains:" may be followed by content outside a clean text node
        contains_match = re.search(r"Contains:\s*([^\n<]+)", html)
        result["contains"] = contains_match.group(1).strip() if contains_match else None

        return result


def main():
    scraper = DiningScraper()

    # Test values confirmed from browser Network tab:
    # Ikenberry Dining Center -> Baked Expectations -> Lunch -> Oct 1, 2026
    TEST_UNIT_OID = 2
    TEST_MENU_OID = 1448442

    print("=" * 70)
    print("STEP 1: Fetching menu item list")
    print("=" * 70)

    items = scraper.get_menu_items(TEST_UNIT_OID, TEST_MENU_OID)

    print(f"\nFound {len(items)} menu items:\n")
    for item in items:
        print(f"  [{item['category']}] {item['name']}")
        print(f"    detail_oid: {item['detail_oid']}")
        print(f"    serving_size: {item['serving_size']}")
        print(f"    allergens: {item['allergens']}")
        print()

    if not items:
        print("No items found — check unitOid/menuOid values or HTML parsing logic.")
        return

    print("=" * 70)
    print("STEP 2: Fetching full nutrition detail for each item")
    print("=" * 70)

    full_data = []
    for item in items:
        if not item["detail_oid"]:
            continue

        print(f"\nFetching nutrition for: {item['name']} (detailOid={item['detail_oid']})")
        nutrition = scraper.get_nutrition_detail(item["detail_oid"])

        combined = {**item, **nutrition}
        full_data.append(combined)

        print(f"  Calories: {nutrition.get('kcal')}")
        print(f"  Raw nutrients: {json.dumps(nutrition.get('raw_nutrients', {}), indent=4)}")
        print(f"  Contains: {nutrition.get('contains')}")

        time.sleep(0.5)  # be polite to the server

    # Save everything to a JSON file for inspection
    with open("scraped_menu_data.json", "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"✓ Done! Scraped {len(full_data)} items with full nutrition data.")
    print("✓ Saved to scraped_menu_data.json")
    print("=" * 70)


if __name__ == "__main__":
    main()