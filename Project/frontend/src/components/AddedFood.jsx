import { useEffect, useState } from 'react'
import { deleteFoodLog, getFoodLogs } from '../api'
import { todayISO } from '../constants'
import { fmt, fmtDate, mealLabel } from '../format'
import QuickAddButton from './QuickAdd'
import { Card } from './ui'

// The day's quick adds (food that isn't on a dining hall menu), each removable, and "+ Add food". Menu dishes are
// checked off on the Plan page; these have no menu to go back to, so this is where they can be seen and fixed.
// `onChanged` runs after an add or a removal, so the page can reload its totals.
export default function AddedFoodCard({ userId, date, onChanged }) {
  const [state, setState] = useState({ key: null })
  const [version, setVersion] = useState(0)
  const [removing, setRemoving] = useState(null) // id of the entry being removed
  const [error, setError] = useState('')
  const key = `${userId}|${date}`

  useEffect(() => {
    let ignore = false
    getFoodLogs(userId, date)
      // A quick add has no menu item; its name and nutrients are on the log itself
      .then((logs) => !ignore && setState({ key, foods: logs.filter((l) => l.item_id == null) }))
      .catch((err) => !ignore && setState({ key, foods: [], loadError: err.message }))
    return () => {
      ignore = true
    }
  }, [key, userId, date, version])

  const changed = () => {
    setVersion((v) => v + 1)
    onChanged()
  }

  const remove = async (food) => {
    setRemoving(food.id)
    setError('')
    try {
      await deleteFoodLog(userId, food.id)
      changed()
    } catch (err) {
      setError(err.message)
    } finally {
      setRemoving(null)
    }
  }

  const foods = state.key === key ? state.foods : null
  const future = date > todayISO()
  // Nothing added and nothing that can be added (a future day): no card at all
  if (future && !foods?.length) return null

  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-bold">Added food</h2>
          <p className="text-[13px] text-muted">Snacks and meals that aren't on a dining hall menu</p>
        </div>
        {!future && (
          <QuickAddButton
            userId={userId}
            date={date}
            onAdded={changed}
            className="shrink-0 rounded-lg bg-brand-soft px-3 py-1.5 text-sm font-semibold text-brand-deep transition-colors hover:bg-brand-soft/70"
          />
        )}
      </div>

      {foods === null ? null : foods.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{state.loadError ? `Couldn't load added food. ${state.loadError}` : `Nothing added ${date === todayISO() ? 'today' : `on ${fmtDate(date)}`}.`}</p>
      ) : (
        <ul className="mt-3 divide-y divide-line text-sm">
          {foods.map((f) => (
            <li key={f.id} className={`flex items-center justify-between gap-3 py-2 ${removing === f.id ? 'opacity-60' : ''}`}>
              <span className="min-w-0">
                <span className="block truncate font-medium">{f.name}</span>
                <span className="text-[12px] text-muted">
                  {mealLabel(f.meal)}
                  {/* Macros left out count as 0 */}
                  {f.protein_g || f.carbs_g || f.fat_g ? ` · ${fmt(f.protein_g ?? 0)}P ${fmt(f.carbs_g ?? 0)}C ${fmt(f.fat_g ?? 0)}F` : ''}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <span className="font-semibold">{fmt(f.kcal)} kcal</span>
                <button
                  type="button"
                  onClick={() => remove(f)}
                  disabled={removing !== null}
                  aria-label={`Remove ${f.name}`}
                  className="grid h-8 w-8 place-items-center rounded-full text-muted transition-colors hover:bg-bg hover:text-bad disabled:opacity-40"
                >
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                    <path d="M6 6l12 12M18 6 6 18" />
                  </svg>
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-bad">
          {error}
        </p>
      )}
    </Card>
  )
}
