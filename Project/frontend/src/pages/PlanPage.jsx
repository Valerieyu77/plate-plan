import { useEffect, useMemo, useState } from 'react'
import { addFoodLog, deleteFoodLog, getFoodLogs, getHalls, getMealTarget, getMeals, getMenuItems, getRecommendations } from '../api'
import { Button, Card, ChipScroller, DateChip, ErrorNote, Input, Label, Loading, PageHeader, ProgressRing } from '../components/ui'
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

// "light lunch" -> "Light lunch"
const mealLabel = (meal) => meal.charAt(0).toUpperCase() + meal.slice(1)

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
    <section>
      <PageHeader title="Plan a meal" sub="Dishes that clash with your allergies or diet are hidden." action={<DateChip value={date} onChange={setDate} />} />

      <div className="space-y-4">
        <div>
          <Label className="mb-2">Dining hall</Label>
          {halls.error ? (
            <ErrorNote>{halls.error.message}</ErrorNote>
          ) : !hallList ? (
            <Loading />
          ) : hallList.length === 0 ? (
            <Card className="text-sm text-muted">No menus have been loaded for this date yet. Try another day.</Card>
          ) : (
            <ChipScroller label="Dining hall" options={hallList} value={hall} onChange={pickHall} getLabel={shortHall} />
          )}
          {hall && shortHall(hall) !== hall && <p className="mt-1.5 text-[13px] text-muted">{hall}</p>}
        </div>

        {hall && (
          <div>
            <Label className="mb-2">Meal</Label>
            {meals.error && meals.key === mealsKey ? (
              <ErrorNote>{meals.error.message}</ErrorNote>
            ) : !mealList ? (
              <Loading />
            ) : mealList.length === 0 ? (
              <Card className="text-sm text-muted">This hall has no main meals on this date.</Card>
            ) : (
              <ChipScroller label="Meal" options={mealList} value={meal} onChange={setMealPick} getLabel={mealLabel} />
            )}
          </div>
        )}
      </div>

      <div className="mt-6">
        {menuKey && !current && <Loading>Loading the menu…</Loading>}
        {current?.error && <ErrorNote>{current.error.message}</ErrorNote>}
      </div>

      {current && !current.error && (
        <div className="space-y-4">
          <MealTargetCard target={current.target} meal={meal} onSetGoal={onSetGoal} />
          {current.rec && <RecommendationCard rec={current.rec} />}

          <div className="pt-2">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-lg font-bold">Menu</h2>
              <p className="text-[13px] text-muted">
                {current.items.length} dishes · {current.items.filter((i) => logByItem.has(i.id)).length} eaten
              </p>
            </div>
            <Input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search dishes" aria-label="Search dishes" />
            <div className="mt-3">
              <ErrorNote>{actionError}</ErrorNote>
            </div>
            {current.items.length === 0 ? (
              <Card className="mt-3 text-sm text-muted">No dishes on this menu fit your allergies and dietary restrictions.</Card>
            ) : stations.length === 0 ? (
              <p className="mt-3 text-sm text-muted">No dishes match "{search.trim()}".</p>
            ) : (
              <div className="mt-3 space-y-4">
                {stations.map(([station, items]) => (
                  <div key={station}>
                    <Label className="mb-1.5 px-1">{station}</Label>
                    <ul className="divide-y divide-line overflow-hidden rounded-2xl bg-surface shadow-[0_1px_3px_rgba(19,41,75,0.06)]">
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
      <label className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors active:bg-bg ${busy ? 'opacity-60' : ''}`}>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-medium">
            <span className="truncate">{item.name}</span>
            {(item.is_vegan || item.is_vegetarian) && (
              <span className="shrink-0 rounded-full bg-good/10 px-2 py-0.5 text-[11px] font-semibold text-good">{item.is_vegan ? 'Vegan' : 'Veg'}</span>
            )}
          </p>
          <p className="mt-0.5 text-[13px] text-muted">
            <span className="font-medium text-ink">{fmt(item.kcal)} kcal</span> · {fmt(item.protein_g)}P {fmt(item.carbs_g)}C {fmt(item.fat_g)}F
            {serving && ` · ${serving}`}
          </p>
        </div>
        <input type="checkbox" checked={checked} disabled={busy} onChange={onToggle} aria-label={`Ate ${item.name}`} className="peer sr-only" />
        <span
          aria-hidden="true"
          className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-brand/40 ${
            checked ? 'border-brand bg-brand text-white' : 'border-line text-transparent'
          }`}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="m5 12 5 5 9-10" />
          </svg>
        </span>
      </label>
    </li>
  )
}

function MealTargetCard({ target, meal, onSetGoal }) {
  if (target.missingGoal) {
    return (
      <Card>
        <p className="font-medium">Set a goal first so we know how much this meal should be.</p>
        <Button onClick={onSetGoal} className="mt-4 w-full">
          Pick a goal
        </Button>
      </Card>
    )
  }
  const left = target.target
  const eaten = target.consumed_this_meal
  const budget = target.meal_budget
  return (
    <Card className="flex items-center gap-5">
      <ProgressRing value={eaten.kcal} max={budget.kcal} size={120} stroke={11} label={`${fmt(eaten.kcal)} of ${fmt(budget.kcal)} kcal eaten at ${meal}`}>
        <p className="text-2xl leading-none font-bold">{fmt(left.kcal)}</p>
        <p className="mt-1 text-[11px] font-medium text-muted">kcal left</p>
      </ProgressRing>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-brand">{mealLabel(meal)} budget</p>
        <p className="mt-0.5 text-sm text-muted">
          {fmt(eaten.kcal)} of {fmt(budget.kcal)} kcal eaten
        </p>
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[
            ['Protein', left.protein_g],
            ['Carbs', left.carbs_g],
            ['Fat', left.fat_g],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl bg-bg py-2">
              <dd className="text-[15px] font-bold">{fmt(value)}g</dd>
              <dt className="text-[11px] text-muted">{label}</dt>
            </div>
          ))}
        </dl>
      </div>
    </Card>
  )
}

function RecommendationCard({ rec }) {
  return (
    <Card tone="bg-ink" className="text-white">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold text-brand">Recommended for you</p>
        {rec.sample && <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-[11px] font-semibold text-white/70">Sample</span>}
      </div>
      {rec.items.length > 0 && (
        <ol className="mt-3 space-y-2">
          {rec.items.map((r, idx) => (
            <li key={r.item_id ?? r.name} className="flex items-center gap-3 rounded-xl bg-white/5 px-3 py-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[12px] font-bold">{idx + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">
                  {r.name}
                  {r.servings !== 1 && <span className="ml-1.5 text-[13px] text-white/60">× {r.servings}</span>}
                </p>
                <p className="text-[12px] text-white/60">
                  {fmt(r.kcal)} kcal · {fmt(r.protein_g)}g protein
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {rec.items.length > 0 && (
        <p className="mt-3 text-sm text-white/70">
          Total <span className="font-semibold text-white">{fmt(rec.total.kcal)} kcal</span> · {fmt(rec.total.protein_g)}P {fmt(rec.total.carbs_g)}C{' '}
          {fmt(rec.total.fat_g)}F
        </p>
      )}
      {rec.note && <p className="mt-2 text-[13px] text-white/60">{rec.note}</p>}
    </Card>
  )
}
