// Every call to the FastAPI backend goes through this file. See Docs/API.md for the shapes.
// To point at the deployed backend, set VITE_API_URL in .env.local (or in Vercel's settings).
export const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// FastAPI errors are {"detail": "..."}, or for 422 {"detail": [{"loc": [...], "msg": "..."}]}
function detailMessage(data) {
  const detail = data?.detail
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d.loc ? `${d.loc.filter((p) => p !== 'body').join('.')}: ${d.msg}` : d.msg)).join('; ')
  }
  return JSON.stringify(detail)
}

async function request(path, { method = 'GET', body, query } = {}) {
  const url = new URL(API_URL + path)
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }

  let res
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, `Can't reach the server at ${API_URL}. Is the backend running?`)
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailMessage(data) || `Request failed (${res.status})`)
  return data
}

// ---------- Users and goals ----------

export const createUser = (user) => request('/users', { method: 'POST', body: user })
export const getUser = (userId) => request(`/users/${userId}`)

export const setGoal = (userId, goalType) => request(`/users/${userId}/goal`, { method: 'PUT', body: { goal_type: goalType } })
export const getGoal = (userId) => request(`/users/${userId}/goal`)

// ---------- Menus ----------

export const getHalls = (date) => request('/halls', { query: { date } })
export const getMeals = (hall, date) => request('/meals', { query: { hall, date, main_only: true } })
export const getMenuItems = ({ hall, date, meal, userId }) =>
  request('/menu-items', { query: { hall, date, meal, user_id: userId } })

export const getMealTarget = (userId, date, meal) => request(`/users/${userId}/meal-target`, { query: { date, meal } })

// ---------- Logs and progress ----------

export const getFoodLogs = (userId, date) => request(`/users/${userId}/food-logs`, { query: { date } })
export const addFoodLog = (userId, itemId, servings = 1) =>
  request(`/users/${userId}/food-logs`, { method: 'POST', body: { item_id: itemId, servings } })
export const deleteFoodLog = (userId, logId) => request(`/users/${userId}/food-logs/${logId}`, { method: 'DELETE' })

export const getWeightLogs = (userId) => request(`/users/${userId}/weight-logs`)
export const addWeightLog = (userId, date, weightLbs) =>
  request(`/users/${userId}/weight-logs`, { method: 'POST', body: { date, weight_lbs: weightLbs } })

export const getProgress = (userId, date) => request(`/users/${userId}/progress`, { query: { date } })

// ---------- Recommendations (sample data for now) ----------

// GET /recommendations/meals isn't built yet (it waits on recommend() from D). Until then this
// returns sample dishes in the same shape the endpoint will return. When the endpoint exists,
// replace the body with:
//   return request('/recommendations/meals', { query: { user_id: userId, hall, date, meal } })
const SAMPLE_PICKS = [
  { item_id: null, name: 'Herb-roasted chicken thigh', servings: 1, kcal: 340, protein_g: 34, carbs_g: 2, fat_g: 21 },
  { item_id: null, name: 'Brown rice pilaf', servings: 1, kcal: 210, protein_g: 5, carbs_g: 42, fat_g: 3 },
  { item_id: null, name: 'Garlic broccoli', servings: 1.5, kcal: 105, protein_g: 7.5, carbs_g: 18, fat_g: 1.5 },
]

// eslint-disable-next-line no-unused-vars
export async function getRecommendations({ userId, hall, date, meal, target }) {
  const total = SAMPLE_PICKS.reduce(
    (t, i) => ({ kcal: t.kcal + i.kcal, protein_g: t.protein_g + i.protein_g, carbs_g: t.carbs_g + i.carbs_g, fat_g: t.fat_g + i.fat_g }),
    { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  )
  return { items: SAMPLE_PICKS, total, target, note: 'Sample dishes: live recommendations are not connected yet.', sample: true }
}
