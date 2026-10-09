// There is no login on the backend yet: the user id in localStorage is the whole session.
// We also remember every account created in this browser so "Log in" can find them by email.
// Clearing the browser's site data loses them; fine for the demo.

const USER_KEY = 'platePlan.userId'
const ACCOUNTS_KEY = 'platePlan.accounts'
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

export const getUserId = () => read(USER_KEY, null)
export const setUserId = (id) => write(USER_KEY, id)
export const clearUserId = () => write(USER_KEY, null)

export const getAccounts = () => read(ACCOUNTS_KEY, [])

export function rememberAccount({ id, name, email }) {
  const others = getAccounts().filter((a) => a.id !== id && a.email.toLowerCase() !== email.toLowerCase())
  write(ACCOUNTS_KEY, [{ id, name, email }, ...others])
}

export function forgetAccount(id) {
  write(ACCOUNTS_KEY, getAccounts().filter((a) => a.id !== id))
}

export const findAccountByEmail = (email) =>
  getAccounts().find((a) => a.email.toLowerCase() === email.trim().toLowerCase()) || null

// Things the backend doesn't store yet: the chosen goal type and the target weight
export const getPrefs = (userId) => read(prefsKey(userId), {})
export const setPrefs = (userId, prefs) => write(prefsKey(userId), { ...getPrefs(userId), ...prefs })
