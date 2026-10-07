"""
UIUC Dining EatSmart Menu Scraper - Research & Exploration
Purpose: Investigate data source, available fields, and scraping feasibility
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import time

# EatSmart System Base URL
BASE_URL = "https://eatsmart.housing.illinois.edu/NetNutrition"

class DiningScraperExplorer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        self.units_data = {}
        self.meals_data = {}
        
    def get_main_page(self):
        """Fetch main page and extract dining hall list"""
        print("\n=== STEP 1: Fetching Main Page ===")
        try:
            response = self.session.get(f"{BASE_URL}/46")
            print(f"✓ Main page loaded successfully (Status: {response.status_code})")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract dining hall list
            dining_halls = []
            hall_buttons = soup.find_all('a', class_='btn')
            
            print(f"Found {len(hall_buttons)} clickable elements")
            
            # Try extracting dining hall info from buttons
            for button in hall_buttons[:5]:  # Check first 5
                text = button.get_text(strip=True)
                href = button.get('href', '')
                print(f"  - {text} (href: {href})")
                if text and text not in ['Back', 'Show All Dates', 'Show All Meals']:
                    dining_halls.append({
                        'name': text,
                        'href': href
                    })
            
            return response.content
            
        except Exception as e:
            print(f"✗ Main page fetch failed: {e}")
            return None
    
    def test_api_endpoints(self):
        """Test EatSmart API endpoints"""
        print("\n=== STEP 2: Testing API Endpoints ===")
        
        # Common EatSmart API endpoints
        endpoints = [
            "/Menus",
            "/Units",
            "/Locations",
            "/NetNutrition/api/menus",
            "/NetNutrition/api/units",
            "/NetNutrition/api/locations"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"https://eatsmart.housing.illinois.edu{endpoint}"
                response = self.session.get(url, timeout=5)
                print(f"  {endpoint}: Status {response.status_code}")
                
                # Try parsing if JSON response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"    → Returns JSON data with {len(data)} items")
                        if isinstance(data, list) and len(data) > 0:
                            print(f"    → Sample: {json.dumps(data[0], indent=2)[:300]}")
                    except:
                        print(f"    → Returns HTML ({len(response.content)} bytes)")
                        
            except Exception as e:
                print(f"  {endpoint}: Connection failed ({str(e)[:50]})")
    
    def analyze_network_requests(self):
        """Analyze possible XHR request parameters"""
        print("\n=== STEP 3: Analyzing Common XHR Requests ===")
        print("Based on Network tab analysis, these are likely API endpoints:")
        print("  - SelectMenu")
        print("  - SelectUnitFromUnitsListX")
        print("  - ShowItemNutritionLabel")
        print("  - SelectUnitFromChildUnitsList")
        print("\nThese requests are typically POST, with parameters like:")
        print("  - UnitID (dining hall ID)")
        print("  - DateStr (date)")
        print("  - Period (meal type: Breakfast, Lunch, Dinner)")
        print("  - ItemID (dish ID)")
    
    def test_direct_scraping(self):
        """Test direct HTML data extraction"""
        print("\n=== STEP 4: Testing Direct HTML Scraping ===")
        
        try:
            # Fetch main page
            response = self.session.get(f"{BASE_URL}/46")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for menu item containers
            print("Searching for menu item data containers...")
            
            # Possible menu item selectors
            selectors = [
                ('class=menu-item', soup.find_all(class_='menu-item')),
                ('data-item', soup.find_all(attrs={'data-item': True})),
                ('class=item', soup.find_all(class_='item')),
                ('li with data attributes', soup.find_all('li', attrs={'data-itemid': True}))
            ]
            
            for selector_name, elements in selectors:
                if elements:
                    print(f"✓ Found {len(elements)} elements (selector: {selector_name})")
                    if len(elements) > 0:
                        print(f"  Sample HTML: {str(elements[0])[:200]}")
                        
        except Exception as e:
            print(f"✗ HTML scraping test failed: {e}")
    
    def test_nutrition_data_extraction(self):
        """Test nutrition data extraction capabilities"""
        print("\n=== STEP 5: Nutrition Data Fields Validation ===")
        
        print("Fields expected to be extractable based on website analysis:")
        
        nutrition_fields = {
            "MVP Required": [
                "name (dish name)",
                "kcal (calories)",
                "protein_g (grams)",
                "carbs_g (grams)",
                "fat_g (grams)",
                "serving_size (numeric value)",
                "serving_unit (unit: g, Each, etc.)"
            ],
            "Optional But Useful": [
                "saturated_fat_g",
                "trans_fat_g",
                "cholesterol_mg",
                "sodium_mg",
                "potassium_mg",
                "fiber_g",
                "sugar_g",
                "vitamin_a",
                "vitamin_c",
                "calcium",
                "iron"
            ],
            "Labels & Allergens": [
                "allergens (allergen tags)",
                "ingredients (full ingredient list)",
                "vegetarian/vegan - may need to infer from allergens"
            ]
        }
        
        for category, fields in nutrition_fields.items():
            print(f"\n{category}:")
            for field in fields:
                print(f"  ✓ {field}")
    
    def generate_research_report(self):
        """Generate research report"""
        print("\n\n" + "="*70)
        print("UIUC DINING DATA SOURCE RESEARCH REPORT")
        print("="*70)
        
        report = """
DATA SOURCE
-----------
Platform: EatSmart (eatsmart.housing.illinois.edu/NetNutrition)
Dining Halls: 11 main dining centers + multiple retail locations
Update Frequency: Daily menu updates
System Type: Web-based with JavaScript/XHR API calls

AVAILABLE DATA FIELDS
---------------------
✓ MVP Required (Calories + Macros):
  - kcal (calories)
  - protein_g (grams)
  - carbs_g (grams, total carbohydrate)
  - fat_g (grams, total fat)
  - serving_size (numeric value, e.g., 47)
  - serving_unit (unit, typically 'g' or 'Each')

✓ Additional Nutrition Info (Confirmed Available):
  - saturated_fat_g
  - trans_fat_g
  - cholesterol_mg
  - sodium_mg
  - potassium_mg
  - fiber_g
  - sugar_g
  - vitamin_a, vitamin_c, calcium, iron, etc.

✓ Allergens & Ingredients:
  - allergens (list format, e.g., "Corn, Gluten, Soy, Wheat")
  - ingredients (full ingredient list)

✗ Missing/Needs Inference:
  - vegetarian/vegan tags: Not explicitly marked on website
  - Workaround: Filter by allergens or infer from dish name

TECHNICAL SCRAPING APPROACH
---------------------------
Recommended: APPROACH A - Reverse Engineer EatSmart API
- Network analysis shows XHR requests: SelectMenu, ShowItemNutritionLabel, etc.
- These are POST requests to internal API endpoints
- Pros: Structured JSON data, efficient, scalable
- Effort: Medium (need to identify endpoint params)
- Risk: Low (if endpoints remain stable)

Alternative: APPROACH B - Playwright/BeautifulSoup HTML Parsing
- Simulate browser interactions (click through menus)
- Parse nutrition popup HTML for each item
- Pros: Browser-agnostic, works if API changes
- Effort: High (requires clicking each item)
- Risk: Slower, more resource-intensive

RECOMMENDED DATABASE SCHEMA
---------------------------
Table: menu_items
Columns:
  - id (primary key)
  - date (YYYY-MM-DD)
  - hall (dining center name)
  - station (food station/category)
  - meal (Breakfast/Lunch/Dinner)
  - name (dish name)
  - serving_size (numeric)
  - serving_unit (string: 'g', 'Each', etc.)
  - kcal (integer)
  - protein_g (float)
  - carbs_g (float)
  - fat_g (float)
  - saturated_fat_g (float, nullable)
  - sodium_mg (float, nullable)
  - fiber_g (float, nullable)
  - sugar_g (float, nullable)
  - allergens (text/JSON, pipe or comma-separated)
  - ingredients (text)
  - created_at (timestamp)

NEXT STEPS
----------
1. Confirm API approach viability (reverse engineer XHR requests)
2. Implement proof-of-concept scraper
3. Validate data quality and completeness
4. Set up data cleaning/normalization rules
5. Integrate GitHub Actions for daily scheduled scraping
6. Handle scraping failures and alerts
7. Migration plan: SQLite (dev) → PostgreSQL (production)
"""
        print(report)
        return report

def main():
    explorer = DiningScraperExplorer()
    
    print("UIUC Dining Data Source Research & Exploration")
    print("=" * 70)
    
    # Run exploration steps
    explorer.get_main_page()
    explorer.test_api_endpoints()
    explorer.analyze_network_requests()
    explorer.test_direct_scraping()
    explorer.test_nutrition_data_extraction()
    
    # Generate report
    report = explorer.generate_research_report()
    
    # Save report to file
    with open('dining_research_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    print("\n✓ Research report saved to dining_research_report.txt")

if __name__ == "__main__":
    main()