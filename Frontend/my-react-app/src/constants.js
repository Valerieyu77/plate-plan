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
  lose: { label: 'Lose weight', note: '−450 kcal a day below maintenance' },
  maintain: { label: 'Maintain', note: 'Eat what your body uses' },
  gain: { label: 'Gain muscle', note: '+400 kcal a day above maintenance' },
}

// YYYY-MM-DD in the user's local time zone (toISOString alone would use UTC)
export function todayISO() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
