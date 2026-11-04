// Values the backend accepts. Keep these in sync with Project/backend/app/models.py and app/dietary.py.

// Allergy names as the dining site tags them (matching is case-insensitive on the backend)
export const ALLERGIES = [
  'Milk', 'Eggs', 'Fish', 'Shellfish', 'Peanuts', 'Tree Nuts', 'Soy', 'Wheat', 'Gluten',
  'Sesame', 'Corn', 'Coconut', 'Sulfites', 'MSG', 'Red Dye',
]

export const DIETARY_RESTRICTIONS = ['vegetarian', 'vegan', 'kosher', 'halal', 'jain', 'no pork', 'no alcohol', 'no gelatin']

// activity_level must be exactly one of these five values
export const ACTIVITY_LEVELS = [
  { value: 'sedentary', label: 'Not active' },
  { value: 'light', label: '1–3 times a week' },
  { value: 'moderate', label: '4–5 times a week' },
  { value: 'active', label: 'Almost every day' },
  { value: 'very_active', label: 'Multiple times a day' },
]

export const GOALS = {
  lose: { label: 'Lose weight', note: 'Pick a target weight and date; we set a safe daily calorie budget.' },
  maintain: { label: 'Maintain', note: 'Eat what your body uses.' },
  gain: { label: 'Gain muscle', note: 'Pick a target weight and date; we add calories at a safe pace.' },
}

// YYYY-MM-DD in the user's local time zone (toISOString alone would use UTC)
export function todayISO() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// The three meals people think in. The data keeps the dining site's own names (light lunch, kosher lunch...),
// which the backend groups under these (see GET /meal-options).
export const MEAL_GROUPS = ['breakfast', 'lunch', 'dinner']

// The meal that fits the time of day: breakfast, lunch or dinner
export function defaultGroup() {
  const hour = new Date().getHours()
  return hour < 10 ? 'breakfast' : hour < 15 ? 'lunch' : 'dinner'
}
