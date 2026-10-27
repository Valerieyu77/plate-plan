// Small formatting helpers shared by the Plan page and its cards, so a hall or meal can't read
// differently in two places.

export const fmt = (n) => (n == null ? '—' : Math.round(n))

// "Ikenberry Dining Center (Ike)" -> "Ike" for compact buttons; the full name is still what we send
export const shortHall = (hall) => hall.match(/\(([^)]+)\)\s*$/)?.[1] || hall

// "light lunch" -> "Light lunch"
export const mealLabel = (meal) => meal.charAt(0).toUpperCase() + meal.slice(1)

// "2026-12-20" -> "Dec 20" (or "Dec 20, 2027" outside this year), read as a local date
export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00`)
  const opts = { month: 'short', day: 'numeric', ...(d.getFullYear() !== new Date().getFullYear() && { year: 'numeric' }) }
  return d.toLocaleDateString(undefined, opts)
}

// Local YYYY-MM-DD, `days` from today
export function isoInDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
