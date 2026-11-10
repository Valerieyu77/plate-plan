// Values the backend accepts. Keep these in sync with Project/backend/app/models.py and app/dietary.py.

// Allergy names as the dining site tags them (matching is case-insensitive on the backend)
export const ALLERGIES = [
  'Milk', 'Eggs', 'Fish', 'Shellfish', 'Peanuts', 'Tree Nuts', 'Soy', 'Wheat', 'Gluten',
  'Sesame', 'Corn', 'Coconut', 'Sulfites', 'MSG', 'Red Dye',
]

// The calorie formula (Mifflin-St Jeor) is made for adults; children and young teens need a doctor's advice instead.
// The backend refuses younger sign-ups and profile edits too (MIN_AGE in app/nutrition.py, keep in sync).
export const MIN_AGE = 16

// The latest birthday allowed: MIN_AGE years before today, local time (Feb 29 becomes Feb 28)
export function latestBirthdate() {
  const d = new Date()
  const year = d.getFullYear() - MIN_AGE
  const day = Math.min(d.getDate(), new Date(year, d.getMonth() + 1, 0).getDate())
  return `${year}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

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

// Muscle groups GET /users/{id}/workout understands (app/exercises.py MUSCLES); "heart" means cardio
export const MUSCLE_GROUPS = [
  { value: 'legs', label: 'Legs' },
  { value: 'glutes', label: 'Glutes' },
  { value: 'chest', label: 'Chest' },
  { value: 'back', label: 'Back' },
  { value: 'shoulders', label: 'Shoulders' },
  { value: 'arms', label: 'Arms' },
  { value: 'core', label: 'Core' },
  { value: 'heart', label: 'Cardio' },
]

export const INTENSITIES = [
  ['light', 'Light'],
  ['moderate', 'Moderate'],
  ['hard', 'Hard'],
]

// The three meals people think in. The data keeps the dining site's own names (light lunch, kosher lunch...),
// which the backend groups under these (see GET /meal-options).
export const MEAL_GROUPS = ['breakfast', 'lunch', 'dinner']

// Share of the day's calories for each meal when all three are eaten (SLOT_WEIGHT in app/nutrition.py, keep in sync).
// A user who skips a meal shares the day between the others in the same proportions.
export const MEAL_WEIGHTS = { breakfast: 25, lunch: 35, dinner: 40 }

// The meal that fits the time of day: breakfast, lunch or dinner. With the meals the user eats (user.meals,
// null for all three), a skipped meal moves on to the next one they eat today, or else back to the last one.
export function defaultGroup(meals) {
  const hour = new Date().getHours()
  const now = hour < 10 ? 'breakfast' : hour < 15 ? 'lunch' : 'dinner'
  if (!meals?.length || meals.includes(now)) return now
  const later = MEAL_GROUPS.slice(MEAL_GROUPS.indexOf(now)).find((m) => meals.includes(m))
  return later || MEAL_GROUPS.filter((m) => meals.includes(m)).at(-1)
}
