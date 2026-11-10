import { useEffect, useState } from 'react'
import { deleteFoodLog, getFoodLogs } from '../api'
import { todayISO } from '../constants'
import { fmt, fmtDate, mealLabel, shortHall } from '../format'
import QuickAddButton from './QuickAdd'
import { Card } from './ui'

// Menus use the dining site's names ("light lunch", "kosher dinner"); list them under the meal people think of
const SECTIONS = ['breakfast', 'lunch', 'dinner', 'snack']
const sectionOf = (meal) => SECTIONS.find((s) => meal?.toLowerCase().includes(s)) || 'snack'

const servingsText = (n) => `${n} ${n === 1 ? 'serving' : 'servings'}`

// Everything logged on `date`, by meal: menu dishes (with their hall and servings) and quick adds, each removable,
// plus "+ Add food" for something that isn't on a menu. This is where a misclick can be seen and taken back.
// `onChanged` runs after an add or a removal, so the page can reload its totals; `version` going up (the page
// logged something itself) reloads the list.
export default function AddedFoodCard({ userId, date, onChanged, version = 0 }) {
  const [state, setState] = useState({ key: null })
  const [ownVersion, setOwnVersion] = useState(0)
  const [removing, setRemoving] = useState(null) // id of the entry being removed
  const [error, setError] = useState('')
  const key = `${userId}|${date}`

  useEffect(() => {
    let ignore = false
    getFoodLogs(userId, date)
      .then((logs) => !ignore && setState({ key, foods: logs }))
      .catch((err) => !ignore && setState({ key, foods: [], loadError: err.message }))
    return () => {
      ignore = true
    }
  }, [key, userId, date, version, ownVersion])

  const changed = () => {
    setOwnVersion((v) => v + 1)
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
  // Nothing logged and nothing that can be logged (a future day): no card at all
  if (future && !foods?.length) return null

  const total = (foods || []).reduce((sum, f) => sum + (f.kcal || 0), 0)
  const sections = SECTIONS.map((s) => [s, (foods || []).filter((f) => sectionOf(f.meal) === s)]).filter(([, list]) => list.length)

  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-bold">Food logged</h2>
          <p className="text-[13px] text-muted">
            {foods?.length ? `${fmt(total)} kcal ${date === todayISO() ? 'today' : `on ${fmtDate(date)}`} · tap × to remove a mistake` : 'Menu dishes and anything you added'}
          </p>
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
        <p className="mt-3 text-sm text-muted">{state.loadError ? `Couldn't load your food log. ${state.loadError}` : `Nothing logged ${date === todayISO() ? 'today' : `on ${fmtDate(date)}`} yet.`}</p>
      ) : (
        <div className="mt-3 space-y-3">
          {sections.map(([section, list]) => (
            <div key={section}>
              <p className="text-[12px] font-semibold tracking-wide text-muted uppercase">{mealLabel(section)}</p>
              <ul className="divide-y divide-line text-sm">
                {list.map((f) => (
                  <li key={f.id} className={`flex items-center justify-between gap-3 py-2 ${removing === f.id ? 'opacity-60' : ''}`}>
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{f.name || 'Menu dish'}</span>
                      <span className="text-[12px] text-muted">
                        {f.item_id != null ? `${servingsText(f.servings)}${f.hall ? ` · ${shortHall(f.hall)}` : ''}` : 'Added by you'}
                        {/* Macros left out count as 0 */}
                        {f.protein_g || f.carbs_g || f.fat_g ? ` · ${fmt(f.protein_g ?? 0)}P ${fmt(f.carbs_g ?? 0)}C ${fmt(f.fat_g ?? 0)}F` : ''}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-1">
                      <span className="font-semibold">{f.kcal != null ? `${fmt(f.kcal)} kcal` : ''}</span>
                      <button
                        type="button"
                        onClick={() => remove(f)}
                        disabled={removing !== null}
                        aria-label={`Remove ${f.name || 'this dish'}`}
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
            </div>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-bad">
          {error}
        </p>
      )}
    </Card>
  )
}
