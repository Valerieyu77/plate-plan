// Every call to the FastAPI backend goes through this file. See Docs/API.md for the shapes.
// To point at the deployed backend, set VITE_API_URL in .env.local (or in Vercel's settings).
import { getToken } from './session'

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

// Render's free server sleeps when idle and takes up to a minute to wake. While it wakes, requests
// hang or fail with a network error or a 502/503/504, so we wait and retry, and tell the page (see onWaking).
// Waits between retries: about 60 s in all, enough for a cold start
const RETRY_DELAYS_MS = [3000, 5000, 8000, 12000, 15000, 17000]
const WAKING_STATUSES = [502, 503, 504]
const SLOW_MS = 3000

const wakingListeners = new Set()
let wakingCount = 0
function setWaking(delta) {
  const wasWaking = wakingCount > 0
  wakingCount += delta
  if (wasWaking !== wakingCount > 0) wakingListeners.forEach((fn) => fn(wakingCount > 0))
}

// Calls fn(true) while any request is waiting for the server to wake, fn(false) when none are.
// Returns an unsubscribe function.
export function onWaking(fn) {
  wakingListeners.add(fn)
  return () => wakingListeners.delete(fn)
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function request(path, { method = 'GET', body, query } = {}) {
  const url = new URL(API_URL + path)
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }

  // Show the "waking up" banner if the request is slow or has to be retried
  let waking = false
  const markWaking = () => {
    if (!waking) setWaking(+1)
    waking = true
  }
  const slowTimer = setTimeout(markWaking, SLOW_MS)

  const token = getToken()
  let res
  try {
    for (let attempt = 0; ; attempt++) {
      try {
        res = await fetch(url, {
          method,
          headers: {
            ...(body ? { 'Content-Type': 'application/json' } : {}),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: body ? JSON.stringify(body) : undefined,
        })
        if (!WAKING_STATUSES.includes(res.status) || attempt === RETRY_DELAYS_MS.length) break
      } catch {
        if (attempt === RETRY_DELAYS_MS.length) {
          throw new ApiError(0, `Can't reach the server at ${API_URL}. It may still be waking up; try again in a minute.`)
        }
      }
      markWaking()
      await sleep(RETRY_DELAYS_MS[attempt])
    }
  } finally {
    clearTimeout(slowTimer)
    if (waking) setWaking(-1)
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    // A 401 from anything but the login form means the saved login is gone or expired
    if (res.status === 401 && token) unauthorizedListeners.forEach((fn) => fn())
    throw new ApiError(res.status, detailMessage(data) || `Request failed (${res.status})`)
  }
  return data
}

const unauthorizedListeners = new Set()
// Calls fn() when the server rejects the saved login token. Returns an unsubscribe function.
export function onUnauthorized(fn) {
  unauthorizedListeners.add(fn)
  return () => unauthorizedListeners.delete(fn)
}

// ---------- Accounts ----------

// Both return {token, user}; the caller saves the token (see session.js)
export const signUp = (user) => request('/auth/signup', { method: 'POST', body: user })
export const logIn = (email, password) => request('/auth/login', { method: 'POST', body: { email, password } })
export const getMe = () => request('/auth/me')

// ---------- Users and goals ----------

export const getUser = (userId) => request(`/users/${userId}`)

// `goal` is {goal_type} for a steady pace, or {target_weight_lbs, target_date} for a timeline
export const setGoal = (userId, goal) => request(`/users/${userId}/goal`, { method: 'PUT', body: goal })
export const getGoal = (userId) => request(`/users/${userId}/goal`)
// Checks a timeline without saving: calories, pace, tier (healthy / aggressive / unsafe), issues, safe alternatives
export const previewGoal = (userId, targetWeight, targetDate) =>
  request(`/users/${userId}/goal/preview`, { method: 'POST', body: { target_weight_lbs: targetWeight, target_date: targetDate } })
// Planned vs actual weight; 404 when the goal has no timeline
export const getGoalTimeline = (userId) => request(`/users/${userId}/goal/timeline`)

// ---------- Menus ----------

// With `meal` (breakfast, lunch or dinner), only the halls that serve that meal that day
export const getHalls = (date, meal) => request('/halls', { query: { date, meal } })
// {"lunch": ["light lunch", "lunch"], "dinner": ["dinner"]}: more than one entry means ask which
export const getMealOptions = (hall, date) => request('/meal-options', { query: { hall, date } })
export const getMenuItems = ({ hall, date, meal, userId }) =>
  request('/menu-items', { query: { hall, date, meal, user_id: userId } })

// Which hall suits the next meal best: a match score and a high-protein plate for every hall that serves it
export const getHallPicks = (userId, date, meal) => request(`/users/${userId}/hall-picks`, { query: { date, meal } })

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

// ---------- Workouts ----------

// Every filter is optional; with none set, the goal picks the focus. `muscles` and `avoid` are lists
// (avoid = exercise ids to steer away from, for "Swap"). The same day and filters give the same plan.
export const getWorkout = (userId, { date, focus, intensity, minutes, muscles = [], noEquipment = false, avoid = [] } = {}) =>
  request(`/users/${userId}/workout`, {
    query: { date, focus, intensity, minutes, muscles: muscles.join(','), no_equipment: noEquipment || undefined, avoid: avoid.join(',') },
  })

export const getWorkoutLogs = (userId, date) => request(`/users/${userId}/workout-logs`, { query: { date } })
// `log` is {exercise_id, minutes, intensity, kcal?, date?}; kcal is worked out on the server when left out
export const addWorkoutLog = (userId, log) => request(`/users/${userId}/workout-logs`, { method: 'POST', body: log })
export const deleteWorkoutLog = (userId, logId) => request(`/users/${userId}/workout-logs/${logId}`, { method: 'DELETE' })

// ---------- Recommendations ----------

// `avoid` is a list of item ids to steer away from (the trays already shown), for "Show me another"
export const getRecommendations = ({ userId, hall, date, meal, avoid = [] }) =>
  request('/recommendations/meals', { query: { user_id: userId, hall, date, meal, avoid: avoid.join(',') } })
