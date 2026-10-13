import { useEffect, useMemo, useRef, useState } from 'react'
import { addFoodLog, deleteFoodLog, getFoodLogs, getHalls, getMealTarget, getMeals, getMenuItems, getRecommendations } from '../api'
import { Button, Card, ChipScroller, DateChip, ErrorNote, Input, Label, Loading, PageHeader, ProgressRing } from '../components/ui'
import { todayISO } from '../constants'
import { getPrefs, setPrefs } from '../session'

const fmt = (n) => (n == null ? '—' : Math.round(n))

// Herbs, sauces and garnishes under this many kcal are hidden until "Show all"
const SMALL_KCAL = 20
const isSmall = (item) => item.kcal != null && item.kcal < SMALL_KCAL

// Servings move in half steps
const SERVING_STEP = 0.5
const MAX_SERVINGS = 5

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
  const [flash, setFlash] = useState('')
  const flashTimer = useRef(null)
  const [showSmall, setShowSmall] = useState(false)

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
        // A failed recommendation shouldn't hide the menu; the card shows the error instead
        const rec = target.missingGoal
          ? null
          : await getRecommendations({ userId: user.id, hall, date, meal }).catch((error) => ({ error }))
        if (!ignore) setMenu({ key: menuKey, items, target, logs, rec })
      })
      .catch((error) => !ignore && setMenu({ key: menuKey, error }))
    return () => {
      ignore = true
    }
  }, [menuKey, hall, date, meal, user.id])
  const current = menuKey && menu.key === menuKey ? menu : null

  // item id -> food log, so a checked dish can be un-checked or have its servings changed
  const logByItem = useMemo(() => new Map((current?.logs || []).map((l) => [l.item_id, l])), [current?.logs])

  // What's checked on this menu, for the sticky bar
  const checkedTotal = useMemo(() => {
    const servings = new Map((current?.logs || []).map((l) => [l.item_id, l.servings]))
    let count = 0
    let kcal = 0
    for (const item of current?.items || []) {
      if (!servings.has(item.id)) continue
      count += 1
      kcal += (item.kcal || 0) * servings.get(item.id)
    }
    return { count, kcal }
  }, [current?.items, current?.logs])

  // Clear the "Logged" message timer if the page closes
  useEffect(() => () => clearTimeout(flashTimer.current), [])

  const showFlash = (text) => {
    setFlash(text)
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setFlash(''), 2500)
  }

  // Small dishes stay visible while searching, or once checked, so nothing seems to vanish
  const q = search.trim().toLowerCase()
  const hidingSmall = !showSmall && !q
  const smallCount = useMemo(() => (current?.items || []).filter((i) => isSmall(i) && !logByItem.has(i.id)).length, [current?.items, logByItem])

  const stations = useMemo(() => {
    const groups = new Map()
    for (const item of current?.items || []) {
      if (q && !item.name.toLowerCase().includes(q)) continue
      if (hidingSmall && isSmall(item) && !logByItem.has(item.id)) continue
      const station = item.station || 'Other'
      if (!groups.has(station)) groups.set(station, [])
      groups.get(station).push(item)
    }
    return [...groups.entries()]
  }, [current?.items, q, hidingSmall, logByItem])

  const pickHall = (h) => {
    setHallPick(h)
    setPrefs(user.id, { hall: h })
  }

  // Log `servings` of a dish (0 removes it). The API can't edit a log, so a new amount replaces the old log.
  const logServings = async (item, servings) => {
    const log = logByItem.get(item.id)
    setActionError('')
    setPending((p) => new Set(p).add(item.id))
    try {
      try {
        if (log) await deleteFoodLog(user.id, log.id)
        if (servings > 0) await addFoodLog(user.id, item.id, servings)
      } finally {
        // Logging changes what's left for this meal, so reload both (also after a half-done change)
        const [logs, target] = await Promise.all([getFoodLogs(user.id, date), loadMealTarget(user.id, date, meal)])
        setMenu((m) => (m.key === menuKey ? { ...m, logs, target } : m))
      }
      showFlash(servings === 0 ? `Removed ${item.name}` : log ? `${item.name}: ${servings}× logged` : `Logged ${item.name}`)
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
            {!q && smallCount > 0 && (
              <div className="mt-2 flex items-center justify-between px-1 text-[13px] text-muted">
                <span>
                  {showSmall ? 'Showing' : 'Hiding'} {smallCount} small {smallCount === 1 ? 'item' : 'items'} under {SMALL_KCAL} kcal
                </span>
                <button onClick={() => setShowSmall((v) => !v)} className="font-semibold text-brand">
                  {showSmall ? 'Hide' : 'Show all'}
                </button>
              </div>
            )}
            <div className="mt-3">
              <ErrorNote>{actionError}</ErrorNote>
            </div>
            {current.items.length === 0 ? (
              <Card className="mt-3 text-sm text-muted">No dishes on this menu fit your allergies and dietary restrictions.</Card>
            ) : stations.length === 0 ? (
              <p className="mt-3 text-sm text-muted">{q ? `No dishes match "${search.trim()}".` : 'Only small items on this menu. Tap "Show all" to see them.'}</p>
            ) : (
              <div className="mt-3 space-y-4">
                {stations.map(([station, items]) => (
                  <div key={station}>
                    <Label className="mb-1.5 px-1">{station}</Label>
                    <ul className="divide-y divide-line overflow-hidden rounded-2xl bg-surface shadow-[0_1px_3px_rgba(19,41,75,0.06)]">
                      {items.map((item) => (
                        <DishRow
                          key={item.id}
                          item={item}
                          servings={logByItem.get(item.id)?.servings || 0}
                          busy={pending.has(item.id)}
                          onServings={(n) => logServings(item, n)}
                        />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <LoggedBar count={checkedTotal.count} kcal={checkedTotal.kcal} flash={flash} />
    </section>
  )
}

function DishRow({ item, servings, busy, onServings }) {
  const checked = servings > 0
  const serving = item.serving_size ? `${item.serving_size} ${item.serving_unit || ''}`.trim() : null
  return (
    <li className={`flex items-center gap-2 pr-4 transition-colors ${busy ? 'opacity-60' : ''}`}>
      <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 py-3 pl-4 active:bg-bg">
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
        <input type="checkbox" checked={checked} disabled={busy} onChange={() => onServings(checked ? 0 : 1)} aria-label={`Ate ${item.name}`} className="peer sr-only" />
        {!checked && (
          <span
            aria-hidden="true"
            className="grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 border-line text-transparent transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-brand/40"
          />
        )}
      </label>
      {checked && <ServingStepper name={item.name} servings={servings} busy={busy} onChange={onServings} />}
    </li>
  )
}

// − 1.5 + : at the lowest step, − removes the dish
function ServingStepper({ name, servings, busy, onChange }) {
  const btn = 'grid h-7 w-7 place-items-center rounded-full text-lg leading-none font-semibold transition-colors disabled:opacity-40'
  return (
    <div className="flex shrink-0 items-center gap-1 rounded-full bg-brand-soft p-0.5" role="group" aria-label={`Servings of ${name}`}>
      <button
        type="button"
        disabled={busy}
        onClick={() => onChange(servings - SERVING_STEP)}
        aria-label={servings <= SERVING_STEP ? `Remove ${name}` : `Fewer servings of ${name}`}
        className={`${btn} text-brand active:bg-brand/10`}
      >
        −
      </button>
      <span className="min-w-8 text-center text-sm font-bold text-brand-deep" aria-live="polite">
        {servings}×
      </span>
      <button
        type="button"
        disabled={busy || servings >= MAX_SERVINGS}
        onClick={() => onChange(servings + SERVING_STEP)}
        aria-label={`More servings of ${name}`}
        className={`${btn} bg-brand text-white active:bg-brand-deep`}
      >
        +
      </button>
    </div>
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
      <ProgressRing value={eaten.kcal} max={budget.kcal} size={120} stroke={11} label={`${fmt(eaten.kcal)} of ${fmt(budget.kcal)} kcal logged for ${meal} today, at any hall`}>
        <p className="text-2xl leading-none font-bold">{fmt(left.kcal)}</p>
        <p className="mt-1 text-[11px] font-medium text-muted">kcal left</p>
      </ProgressRing>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-brand">
          {mealLabel(meal)} budget: {fmt(budget.kcal)} kcal
        </p>
        {/* consumed_this_meal counts this meal at every hall, so say so */}
        <p className="mt-0.5 text-sm text-muted">
          Logged for {meal} today (any hall): <span className="font-medium text-ink">{fmt(eaten.kcal)} kcal</span>
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
      <p className="text-[13px] font-semibold text-brand">Recommended for you</p>
      {rec.error && <p className="mt-2 text-sm text-white/70">Couldn't load recommendations: {rec.error.message}</p>}
      {rec.items?.length > 0 && (
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
      {rec.items?.length > 0 && (
        <p className="mt-3 text-sm text-white/70">
          Total <span className="font-semibold text-white">{fmt(rec.total.kcal)} kcal</span> · {fmt(rec.total.protein_g)}P {fmt(rec.total.carbs_g)}C{' '}
          {fmt(rec.total.fat_g)}F
        </p>
      )}
      {rec.note && <p className="mt-2 text-[13px] text-white/60">{rec.note}</p>}
    </Card>
  )
}

// Sticks just above the bottom tab bar: what's checked at this meal, plus a short "Logged" message
function LoggedBar({ count, kcal, flash }) {
  return (
    <div className="pointer-events-none sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-10 mt-6 space-y-2">
      <p role="status" aria-live="polite" className="flex justify-center">
        {flash && (
          <span className="flex items-center gap-1.5 rounded-full bg-ink px-3.5 py-1.5 text-[13px] font-medium text-white shadow-lg">
            <svg viewBox="0 0 24 24" className="h-4 w-4 text-good" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m5 12 5 5 9-10" />
            </svg>
            <span className="max-w-[16rem] truncate">{flash}</span>
          </span>
        )}
      </p>
      {count > 0 && (
        <a
          href="#/progress"
          className="pointer-events-auto flex items-center justify-between rounded-2xl bg-brand px-4 py-3 text-white shadow-[0_6px_20px_rgba(232,74,39,0.35)] transition-colors active:bg-brand-deep"
        >
          <span className="font-semibold">
            {count} {count === 1 ? 'dish' : 'dishes'} · {fmt(kcal)} kcal
          </span>
          <span className="flex items-center gap-1 text-sm font-semibold">
            View progress
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m9 6 6 6-6 6" />
            </svg>
          </span>
        </a>
      )}
    </div>
  )
}
