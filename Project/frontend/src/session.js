// The login token from POST /auth/login or /auth/signup is the whole session: api.js sends it on
// every request, and App asks GET /auth/me who it belongs to when the page loads.

const TOKEN_KEY = 'platePlan.token'
const LAST_EMAIL_KEY = 'platePlan.lastEmail'
const prefsKey = (userId) => `platePlan.prefs.${userId}`

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : JSON.parse(raw)
  } catch {
    return fallback
  }
}

function write(key, value) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage blocked (private window): the app still works until the tab closes
  }
}

export const getToken = () => read(TOKEN_KEY, null)
export const setToken = (token) => write(TOKEN_KEY, token)
export const clearToken = () => write(TOKEN_KEY, null)

// Prefills the log-in form after logging out
export const getLastEmail = () => read(LAST_EMAIL_KEY, '')
export const setLastEmail = (email) => write(LAST_EMAIL_KEY, email)

// Per-user conveniences the backend doesn't need, e.g. the last hall picked on the Plan page
export const getPrefs = (userId) => read(prefsKey(userId), {})
export const setPrefs = (userId, prefs) => write(prefsKey(userId), { ...getPrefs(userId), ...prefs })
