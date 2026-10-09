import { useEffect, useMemo, useState } from 'react'
import { addFoodLog, deleteFoodLog, getFoodLogs, getHalls, getMealTarget, getMeals, getMenuItems, getRecommendations } from '../api'
import { ChoiceChips, ErrorNote, Field, Input, Loading, SectionHead } from '../components/ui'
import { todayISO } from '../constants'
import { getPrefs, setPrefs } from '../session'

const fmt = (n) => (n == null ? '—' : Math.round(n))

// Pre-select the meal that fits the time of day, if the hall serves it
function defaultMeal(meals) {
  const hour = new Date().getHours()
  const wanted = hour < 10 ? ['breakfast'] : hour < 15 ? ['lunch', 'light lunch'] : ['dinner']
  return meals.find((m) => wanted.includes(m)) || meals[0] || null
}

// "Ikenberry Dining Center (Ike)" -> "Ike" for the compact buttons; the full name is still what we send
const shortHall = (hall) => hall.match(/\(([^)]+)\)\s*$/)?.[1] || hall

async function loadMealTarget(userId, date, meal) {
  try {
    return await getMealTarget(userId, date, meal)
  } catch (err) {
    if (err.status === 404) return { missingGoal: true }
    throw err
  }
}

export default function PlanPage({ user, onSetGoal }) {
  const [date, setDate] = useState(todayISO())
  const [hallPick, setHallPick] = useState(() => getPrefs(user.id).hall || null)
  const [mealPick, setMealPick] = useState(null)
  const [halls, setHalls] = useState({ key: null })
  const [meals, setMeals] = useState({ key: null })
  const [menu, setMenu] = useState({ key: null })
  const [pending, setPending] = useState(new Set())
  const [actionError, setActionError] = useState('')
  const [search, setSearch] = useState('')

  // 1. Halls with menus on this date
  useEffect(() => {
    let ignore = false
    getHalls(date)
      .then((list) => !ignore && setHalls({ key: date, list }))
      .catch((error) => !ignore && setHalls({ key: date, list: [], error }))
    return () => {
      ignore = true
    }
  }, [date])
  const hallList = halls.key === date ? halls.list : null
  const hall = hallList ? (hallList.includes(hallPick) ? hallPick : hallList[0] || null) : null

  // 2. Meals that hall serves on this date
  const mealsKey = hall ? `${hall}|${date}` : null
  useEffect(() => {
    if (!mealsKey) return
    let ignore = false
    getMeals(hall, date)
      .then((list) => !ignore && setMeals({ key: mealsKey, list }))
      .catch((error) => !ignore && setMeals({ key: mealsKey, list: [], error }))
    return () => {
      ignore = true
    }
  }, [mealsKey, hall, date])
  const mealList = mealsKey && meals.key === mealsKey ? meals.list : null
  const meal = mealList ? (mealList.includes(mealPick) ? mealPick : defaultMeal(mealList)) : null

  // 3. This meal's target, the dishes the user can eat, today's logs, and the recommendation
  const menuKey = meal ? `${hall}|${date}|${meal}` : null
  useEffect(() => {
    if (!menuKey) return
    let ignore = false
    Promise.all([
      getMenuItems({ hall, date, meal, userId: user.id }),
      loadMealTarget(user.id, date, meal),
      getFoodLogs(user.id, date),
    ])
      .then(async ([items, target, logs]) => {
        const rec = target.missingGoal ? null : await getRecommendations({ userId: user.id, hall, date, meal, target: target.target })
        if (!ignore) setMenu({ key: menuKey, items, target, logs, rec })
      })
      .catch((error) => !ignore && setMenu({ key: menuKey, error }))
    return () => {
      ignore = true
    }
  }, [menuKey, hall, date, meal, user.id])
  const current = menuKey && menu.key === menuKey ? menu : null

  // item id -> food log id, so a checked dish can be un-checked
  const logByItem = useMemo(() => new Map((current?.logs || []).map((l) => [l.item_id, l.id])), [current?.logs])

  const stations = useMemo(() => {
    const q = search.trim().toLowerCase()
    const groups = new Map()
    for (const item of current?.items || []) {
      if (q && !item.name.toLowerCase().includes(q)) continue
      const station = item.station || 'Other'
      if (!groups.has(station)) groups.set(station, [])
      groups.get(station).push(item)
    }
    return [...groups.entries()]
  }, [current?.items, search])

  const pickHall = (h) => {
    setHallPick(h)
    setPrefs(user.id, { hall: h })
  }

  const toggle = async (item) => {
    const logId = logByItem.get(item.id)
    setActionError('')
    setPending((p) => new Set(p).add(item.id))
    try {
      if (logId) await deleteFoodLog(user.id, logId)
      else await addFoodLog(user.id, item.id, 1)
      // Logging changes what's left for this meal, so reload both
      const [logs, target] = await Promise.all([getFoodLogs(user.id, date), loadMealTarget(user.id, date, meal)])
      setMenu((m) => (m.key === menuKey ? { ...m, logs, target } : m))
    } catch (err) {
      setActionError(err.message)
    } finally {
      setPending((p) => {
        const next = new Set(p)
        next.delete(item.id)
        return next
      })
    }
  }

  return (
    <section className="pt-10 pb-24">
      <SectionHead n="02" title="Plan a meal" sub="Pick a dining hall and meal. Dishes that clash with your allergies or diet are already hidden." />

      <div className="mb-10 space-y-6">
        <Field label="Date" className="max-w-[220px]">
          <Input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
        </Field>

        <div>
          <p className="mb-2 font-mono text-[12px] uppercase tracking-wider text-ink-soft">Dining hall</p>
          {halls.error ? (
            <ErrorNote>{halls.error.message}</ErrorNote>
          ) : !hallList ? (
            <Loading />
          ) : hallList.length === 0 ? (
            <p className="text-ink-soft">No menus have been loaded for this date yet. Try another day.</p>
          ) : (
            <ChoiceChips options={hallList} value={hall} onChange={pickHall} getLabel={shortHall} />
          )}
          {hall && <p className="mt-2 text-sm text-ink-soft">{hall}</p>}
        </div>

        {hall && (
          <div>
            <p className="mb-2 font-mono text-[12px] uppercase tracking-wider text-ink-soft">Meal</p>
            {meals.error && meals.key === mealsKey ? (
              <ErrorNote>{meals.error.message}</ErrorNote>
            ) : !mealList ? (
              <Loading />
            ) : mealList.length === 0 ? (
              <p className="text-ink-soft">This hall has no main meals on this date.</p>
            ) : (
              <ChoiceChips options={mealList} value={meal} onChange={setMealPick} />
            )}
          </div>
        )}
      </div>

      {menuKey && !current && <Loading>Loading the menu…</Loading>}
      {current?.error && <ErrorNote>{current.error.message}</ErrorNote>}

      {current && !current.error && (
        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-6 self-start">
            <MealTargetCard target={current.target} meal={meal} onSetGoal={onSetGoal} />
            {current.rec && <RecommendationCard rec={current.rec} />}
          </div>

          <div>
            <div className="mb-4 flex items-end justify-between gap-4">
              <p className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">
                {current.items.length} dishes you can eat · {current.items.filter((i) => logByItem.has(i.id)).length} checked
              </p>
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search dishes" className="max-w-[200px] py-1.5" />
            </div>
            <ErrorNote>{actionError}</ErrorNote>
            {current.items.length === 0 ? (
              <p className="border-y border-ink py-6 text-ink-soft">No dishes on this menu fit your allergies and dietary restrictions.</p>
            ) : (
              <div className="space-y-8">
                {stations.map(([station, items]) => (
                  <div key={station}>
                    <h3 className="mb-1 font-mono text-[12px] uppercase tracking-wider text-illini-deep">{station}</h3>
                    <ul className="divide-y divide-rule border-y border-ink">
                      {items.map((item) => (
                        <DishRow key={item.id} item={item} checked={logByItem.has(item.id)} busy={pending.has(item.id)} onToggle={() => toggle(item)} />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function DishRow({ item, checked, busy, onToggle }) {
  const serving = item.serving_size ? `${item.serving_size} ${item.serving_unit || ''}`.trim() : null
  return (
    <li>
      <label className={`flex cursor-pointer items-center gap-4 py-3 ${busy ? 'opacity-60' : ''}`}>
        <input type="checkbox" checked={checked} disabled={busy} onChange={onToggle} className="h-5 w-5 shrink-0 accent-illini" />
        <div className="min-w-0 flex-1">
          <p className={`font-serif text-lg font-medium ${checked ? 'text-illini-deep' : ''}`}>{item.name}</p>
          <p className="mt-0.5 font-mono text-[12px] text-ink-soft">
            {fmt(item.kcal)} kcal · {fmt(item.protein_g)}P {fmt(item.carbs_g)}C {fmt(item.fat_g)}F{serving && ` · per ${serving}`}
          </p>
        </div>
        {(item.is_vegan || item.is_vegetarian) && (
          <span className="border border-rule px-2 py-0.5 font-mono text-[11px] uppercase text-ink-soft">{item.is_vegan ? 'Vegan' : 'Veg'}</span>
        )}
      </label>
    </li>
  )
}

function MealTargetCard({ target, meal, onSetGoal }) {
  if (target.missingGoal) {
    return (
      <div className="border border-ink p-6">
        <p>Set a goal first so we know how much this meal should be.</p>
        <button onClick={onSetGoal} className="mt-4 bg-ink px-5 py-3 text-sm font-medium text-paper transition-colors hover:bg-illini">
          Pick a goal
        </button>
      </div>
    )
  }
  const t = target.target
  const eaten = target.consumed_this_meal
  return (
    <div className="border border-ink bg-paper-deep/60 p-6">
      <p className="font-mono text-[12px] uppercase tracking-wider text-illini-deep">Left for {meal}</p>
      <div className="mt-3 flex items-end gap-3">
        <span className="font-serif text-6xl leading-none font-medium">{fmt(t.kcal)}</span>
        <span className="pb-1 font-mono text-sm text-ink-soft">kcal</span>
      </div>
      <p className="mt-3 font-mono text-sm">
        {fmt(t.protein_g)}g protein · {fmt(t.carbs_g)}g carbs · {fmt(t.fat_g)}g fat
      </p>
      {eaten.kcal > 0 && (
        <p className="mt-3 border-t border-rule pt-3 text-sm text-ink-soft">
          Already checked at this meal: {fmt(eaten.kcal)} kcal, {fmt(eaten.protein_g)}g protein
        </p>
      )}
    </div>
  )
}

function RecommendationCard({ rec }) {
  return (
    <div className="border border-ink bg-ink p-6 text-paper">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[12px] uppercase tracking-wider text-illini">Recommended</p>
        {rec.sample && <span className="border border-paper/30 px-2 py-0.5 font-mono text-[11px] uppercase text-paper/70">Sample</span>}
      </div>
      <h3 className="mt-3 font-serif text-3xl leading-tight font-medium">Your tray</h3>
      <ol className="mt-5 space-y-4">
        {rec.items.map((r, idx) => (
          <li key={r.item_id ?? r.name} className="flex gap-4 border-t border-paper/20 pt-4">
            <span className="font-mono text-illini">0{idx + 1}</span>
            <div>
              <p className="font-medium">
                {r.name}
                {r.servings !== 1 && <span className="ml-2 font-mono text-[12px] text-paper/70">× {r.servings}</span>}
              </p>
              <p className="font-mono text-[12px] text-paper/60">
                {fmt(r.kcal)} kcal · {fmt(r.protein_g)}g protein
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-5 border-t border-paper/20 pt-4 font-mono text-sm text-paper/70">
        {fmt(rec.total.kcal)} kcal · {fmt(rec.total.protein_g)}P {fmt(rec.total.carbs_g)}C {fmt(rec.total.fat_g)}F
      </p>
      {rec.note && <p className="mt-3 text-sm text-paper/60">{rec.note}</p>}
    </div>
  )
}
