import { useEffect, useMemo, useRef, useState } from 'react'
import { addFoodLog, deleteFoodLog, getFoodLogs, getHalls, getMealOptions, getMealTarget, getMenuItems, getRecommendations } from '../api'
import HallPicks from '../components/HallPicks'
import QuickAddButton from '../components/QuickAdd'
import { Button, Card, ChipScroller, DateChip, ErrorNote, Input, Label, Loading, PageHeader, ProgressRing } from '../components/ui'
import { ALLERGIES, MEAL_GROUPS, defaultGroup, todayISO } from '../constants'
import { fmt, fmtDate, mealLabel, shortHall } from '../format'
import { getPrefs, setPrefs } from '../session'


// "1.5 servings (1 Cup each)": the tray line doesn't say how big a serving is, so use the menu item's
function amountOf(line, item) {
  const count = `${line.servings} ${line.servings === 1 ? 'serving' : 'servings'}`
  return item?.serving_size ? `${count} (${`${item.serving_size} ${item.serving_unit || ''}`.trim()} each)` : count
}

// Herbs, sauces and garnishes under this many kcal are hidden until "Show all"
const SMALL_KCAL = 20
const isSmall = (item) => item.kcal != null && item.kcal < SMALL_KCAL

// Servings move in half steps
const SERVING_STEP = 0.5
const MAX_SERVINGS = 5
// Typing allows any amount up to this, in hundredths (e.g. 0.25 of a pizza, 8 cookies)
const MAX_TYPED_SERVINGS = 20

// A group can have more than one menu (lunch: "light lunch" and "lunch"). Start on the plain one.
const defaultOption = (options) => options.find((o) => o === 'lunch') || options[0] || null

// A tray as a sorted list of dish ids, to tell whether we have shown it before
const trayKey = (rec) => (rec.items || []).map((l) => l.item_id).sort((a, b) => a - b).join(',')

// Dish groups, in the order people eat them; anything else follows alphabetically
const CATEGORY_ORDER = ['Entrees', 'Proteins', 'Starches', 'Vegetables', 'Soups', 'Salads & Salad Bar', 'Appetizers & Sides', 'Breads', 'Cheeses', 'Fruits', 'Desserts']
const categoryRank = (c) => (CATEGORY_ORDER.includes(c) ? CATEGORY_ORDER.indexOf(c) : CATEGORY_ORDER.length)

// The allergens a dish carries, leaving out the labels the dining site mixes in (Kosher, Halal, Local...)
const ALLERGEN_SET = new Set(ALLERGIES.map((a) => a.toLowerCase()))
const allergensOf = (item) => (item.allergens || []).filter((a) => ALLERGEN_SET.has(a.toLowerCase()))

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
  const [groupPick, setGroupPick] = useState(() => defaultGroup(user.meals))
  const [hallPick, setHallPick] = useState(() => getPrefs(user.id).hall || null)
  const [optionPick, setOptionPick] = useState(null)
  const [halls, setHalls] = useState({ key: null })
  const [options, setOptions] = useState({ key: null })
  const [menu, setMenu] = useState({ key: null })
  const [pending, setPending] = useState(new Set())
  const [actionError, setActionError] = useState('')
  const [search, setSearch] = useState('')
  const [flash, setFlash] = useState('')
  const flashTimer = useRef(null)
  const [showSmall, setShowSmall] = useState(false)
  const [recBusy, setRecBusy] = useState(false)
  const [trayBusy, setTrayBusy] = useState(false)
  const [logVersion, setLogVersion] = useState(0) // goes up after every change to what is logged
  const [noMore, setNoMore] = useState(false) // "Show me another" ran out of different plates
  const shownTrays = useRef(new Set()) // the trays already shown for this menu (as sorted id lists)
  const shownDishes = useRef(new Set()) // every dish in them

  // 1. Halls that serve this meal on this date (shops that sell no main meals are not listed)
  const hallsKey = `${date}|${groupPick}`
  useEffect(() => {
    let ignore = false
    getHalls(date, groupPick)
      .then((list) => !ignore && setHalls({ key: hallsKey, list }))
      .catch((error) => !ignore && setHalls({ key: hallsKey, list: [], error }))
    return () => {
      ignore = true
    }
  }, [hallsKey, date, groupPick])
  const hallList = halls.key === hallsKey ? halls.list : null
  const hall = hallList ? (hallList.includes(hallPick) ? hallPick : hallList[0] || null) : null

  // 2. Which menus that hall has for this meal. More than one (light lunch / lunch) means ask.
  const optionsKey = hall ? `${hall}|${date}` : null
  useEffect(() => {
    if (!optionsKey) return
    let ignore = false
    getMealOptions(hall, date)
      .then((byGroup) => !ignore && setOptions({ key: optionsKey, byGroup }))
      .catch((error) => !ignore && setOptions({ key: optionsKey, byGroup: {}, error }))
    return () => {
      ignore = true
    }
  }, [optionsKey, hall, date])
  const optionList = optionsKey && options.key === optionsKey ? options.byGroup[groupPick] || [] : null
  const meal = optionList ? (optionList.includes(optionPick) ? optionPick : defaultOption(optionList)) : null

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
        if (!ignore) {
          rememberTray(rec, true)
          setNoMore(false)
          setMenu({ key: menuKey, items, target, logs, rec })
        }
      })
      .catch((error) => !ignore && setMenu({ key: menuKey, error }))
    return () => {
      ignore = true
    }
  }, [menuKey, hall, date, meal, user.id])
  const current = menuKey && menu.key === menuKey ? menu : null

  // item id -> food log, so a checked dish can be un-checked or have its servings changed
  const logByItem = useMemo(() => new Map((current?.logs || []).map((l) => [l.item_id, l])), [current?.logs])

  const itemsById = useMemo(() => new Map((current?.items || []).map((i) => [i.id, i])), [current?.items])

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

  const categories = useMemo(() => {
    const groups = new Map()
    for (const item of current?.items || []) {
      if (q && !item.name.toLowerCase().includes(q)) continue
      if (hidingSmall && isSmall(item) && !logByItem.has(item.id)) continue
      const category = item.category || 'Other'
      if (!groups.has(category)) groups.set(category, [])
      groups.get(category).push(item)
    }
    return [...groups.entries()].sort(([a], [b]) => categoryRank(a) - categoryRank(b) || a.localeCompare(b))
  }, [current?.items, q, hidingSmall, logByItem])

  const pickHall = (h) => {
    setHallPick(h)
    setPrefs(user.id, { hall: h })
  }

  // The trays already shown, so "Show me another" can tell when it has run out. `reset` starts a new list.
  function rememberTray(rec, reset = false) {
    if (reset) {
      shownTrays.current = new Set()
      shownDishes.current = new Set()
    }
    if (!rec?.items?.length) return
    shownTrays.current.add(trayKey(rec))
    rec.items.forEach((l) => shownDishes.current.add(l.item_id))
  }

  const reloadAfterLogging = async ({ refreshRec = false } = {}) => {
    const [logs, target] = await Promise.all([getFoodLogs(user.id, date), loadMealTarget(user.id, date, meal)])
    // Logging by hand shrinks what is left for this meal, so a tray picked for the old budget is stale: ask again
    const rec = refreshRec && !target.missingGoal ? await getRecommendations({ userId: user.id, hall, date, meal }).catch((error) => ({ error })) : null
    if (rec) rememberTray(rec, true)
    setMenu((m) => (m.key === menuKey ? { ...m, logs, target, ...(rec ? { rec } : {}) } : m))
    if (rec) setNoMore(false)
    setLogVersion((v) => v + 1)
  }

  // Log `servings` of a dish (0 removes it). The API can't edit a log, so a new amount replaces the old one:
  // add the new log first and remove the old one only once that worked, so a failure never loses what was logged.
  const logServings = async (item, servings) => {
    // A future day: nothing new can be logged, but an amount logged earlier can still be lowered or removed
    if (date > todayISO() && servings > (logByItem.get(item.id)?.servings || 0)) return
    const log = logByItem.get(item.id)
    setActionError('')
    setPending((p) => new Set(p).add(item.id))
    try {
      try {
        if (servings > 0) await addFoodLog(user.id, item.id, servings)
        if (log) await deleteFoodLog(user.id, log.id)
      } finally {
        await reloadAfterLogging({ refreshRec: true }) // also after a half-done change
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

  // Log every dish of the recommended tray. All-or-nothing as far as we can: add every new log first, undo them if
  // one fails, and only then remove the entries they replace. The tray's dishes are locked while this runs.
  const logTray = async () => {
    if (date > todayISO()) return
    const lines = current?.rec?.items || []
    const ids = lines.map((l) => l.item_id)
    const created = []
    let step = 'adding'
    setActionError('')
    setTrayBusy(true)
    setPending((p) => new Set([...p, ...ids]))
    try {
      for (const line of lines) created.push(await addFoodLog(user.id, line.item_id, line.servings))
      step = 'replacing'
      for (const line of lines) {
        const old = logByItem.get(line.item_id)
        if (old) await deleteFoodLog(user.id, old.id)
      }
      showFlash(`Logged ${lines.length} ${lines.length === 1 ? 'dish' : 'dishes'}`)
    } catch (err) {
      if (step === 'adding') {
        for (const log of created) await deleteFoodLog(user.id, log.id).catch(() => {}) // leave the day as it was
        setActionError(`Couldn't log this tray, nothing was changed. ${err.message}`)
      } else {
        setActionError(`The tray is logged, but an earlier entry couldn't be removed, so a dish may count twice. ${err.message}`)
      }
    } finally {
      await reloadAfterLogging().catch((err) => setActionError(err.message))
      setPending((p) => {
        const next = new Set(p)
        ids.forEach((id) => next.delete(id))
        return next
      })
      setTrayBusy(false)
    }
  }

  // Ask for a different, similarly good tray. First steer away from the tray on screen; if that gives one
  // already seen, steer away from everything seen; if that repeats too, there is nothing new to show.
  const anotherTray = async () => {
    const ask = (avoid) => getRecommendations({ userId: user.id, hall, date, meal, avoid })
    setActionError('')
    setNoMore(false)
    setRecBusy(true)
    try {
      let rec = await ask((current?.rec?.items || []).map((l) => l.item_id))
      if (shownTrays.current.has(trayKey(rec))) rec = await ask([...shownDishes.current])
      if (!rec.items?.length || shownTrays.current.has(trayKey(rec))) {
        setNoMore(true)
      } else {
        rememberTray(rec)
        setMenu((m) => (m.key === menuKey ? { ...m, rec } : m))
      }
    } catch (err) {
      setActionError(err.message)
    } finally {
      setRecBusy(false)
    }
  }

  // Menus are published ahead, so a later date can be browsed and planned, but not logged as eaten yet
  const future = date > todayISO()

  const trayLogged = (current?.rec?.items || []).length > 0 && current.rec.items.every((l) => logByItem.get(l.item_id)?.servings === l.servings)

  return (
    <section>
      <PageHeader title="Plan a meal" sub="Dishes that clash with your allergies or diet are hidden." action={<DateChip value={date} onChange={setDate} />} />

      <div className="space-y-4">
        <div>
          <Label className="mb-2">Meal</Label>
          <ChipScroller label="Meal" options={MEAL_GROUPS} value={groupPick} onChange={setGroupPick} getLabel={mealLabel} />
        </div>

        <div>
          <Label className="mb-2">Dining hall</Label>
          {halls.error ? (
            <ErrorNote>{halls.error.message}</ErrorNote>
          ) : !hallList ? (
            <Loading />
          ) : hallList.length === 0 ? (
            <Card className="text-sm text-muted">
              No dining hall has {groupPick} on this date. Menus are published about two weeks ahead, so try another day or meal.
            </Card>
          ) : (
            <ChipScroller label="Dining hall" options={hallList} value={hall} onChange={pickHall} getLabel={shortHall} />
          )}
          {hall && shortHall(hall) !== hall && <p className="mt-1.5 text-[13px] text-muted">{hall}</p>}
        </div>

        {hall && (
          <div>
            {options.error && options.key === optionsKey ? (
              <ErrorNote>{options.error.message}</ErrorNote>
            ) : !optionList ? (
              <Loading />
            ) : optionList.length === 0 ? (
              <Card className="text-sm text-muted">This hall doesn't serve {groupPick} on this date.</Card>
            ) : (
              optionList.length > 1 && (
                <>
                  <Label className="mb-2">Which {groupPick}?</Label>
                  <ChipScroller label={`Which ${groupPick}`} options={optionList} value={meal} onChange={setOptionPick} getLabel={mealLabel} />
                </>
              )
            )}
          </div>
        )}
      </div>

      {hall && (
        <div className="mt-5">
          <HallPicks userId={user.id} date={date} group={groupPick} hall={hall} onPickHall={pickHall} version={logVersion} />
        </div>
      )}

      <div className="mt-6">
        {menuKey && !current && <Loading>Loading the menu…</Loading>}
        {current?.error && <ErrorNote>{current.error.message}</ErrorNote>}
      </div>

      {current && !current.error && (
        <div className="space-y-4">
          <MealTargetCard target={current.target} meal={meal} day={date === todayISO() ? 'today' : `on ${fmtDate(date)}`} onSetGoal={onSetGoal} />
          {current.rec && (
            <RecommendationCard
              rec={current.rec}
              itemsById={itemsById}
              logged={trayLogged}
              logBlockedLabel={future ? `Log on ${fmtDate(date)}` : null}
              logBusy={trayBusy}
              anotherBusy={recBusy}
              noMore={noMore}
              onLog={logTray}
              onAnother={anotherTray}
            />
          )}

          <div className="pt-2">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-lg font-bold">Menu</h2>
              <p className="text-[13px] text-muted">
                {current.items.length} dishes{!future && ` · ${current.items.filter((i) => logByItem.has(i.id)).length} eaten`}
              </p>
            </div>
            {future && (
              <p className="mb-3 rounded-xl bg-brand-soft px-3.5 py-2.5 text-sm text-brand-deep">
                This is the menu for {fmtDate(date)}. You can log what you eat on that day.
              </p>
            )}
            {/* Food from elsewhere for this meal: it counts like a dish, so the budget and tray follow */}
            {!future && (
              <div className="mb-3 flex items-center justify-between gap-3 px-1 text-[13px] text-muted">
                <span>Ate something that isn't on this menu?</span>
                <QuickAddButton
                  userId={user.id}
                  date={date}
                  defaultMeal={groupPick}
                  onAdded={(log) => {
                    showFlash(`Added ${log.name}`)
                    reloadAfterLogging({ refreshRec: true }).catch((err) => setActionError(err.message))
                  }}
                  className="shrink-0 font-semibold text-brand"
                />
              </div>
            )}
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
            ) : categories.length === 0 ? (
              <p className="mt-3 text-sm text-muted">{q ? `No dishes match "${search.trim()}".` : 'Only small items on this menu. Tap "Show all" to see them.'}</p>
            ) : (
              <div className="mt-3 space-y-4">
                {categories.map(([category, items]) => (
                  <div key={category}>
                    <Label className="mb-1.5 px-1">{category}</Label>
                    <ul className="divide-y divide-line overflow-hidden rounded-2xl bg-surface shadow-[0_1px_3px_rgba(19,41,75,0.06)]">
                      {items.map((item) => (
                        <DishRow
                          key={item.id}
                          item={item}
                          servings={logByItem.get(item.id)?.servings || 0}
                          busy={pending.has(item.id)}
                          locked={future}
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

// One dish. "+ Ate this" logs a serving, then the stepper changes or removes it. Only the button logs: the row itself
// isn't a tap target, so scrolling the menu can't log a dish by accident.
// locked: a future date, so there is no "Ate this" button. A dish already logged for that day (before logging ahead
// was blocked) keeps its stepper, so it can still be removed.
function DishRow({ item, servings, busy, locked, onServings }) {
  const checked = servings > 0
  const serving = item.serving_size ? `${item.serving_size} ${item.serving_unit || ''}`.trim() : null
  return (
    <li className={`flex items-center gap-3 py-3 pr-4 pl-4 transition-colors ${busy ? 'opacity-60' : ''}`}>
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
        {allergensOf(item).length > 0 && <p className="mt-0.5 text-[12px] text-muted">Contains {allergensOf(item).join(', ')}</p>}
      </div>
      {checked ? (
        <ServingStepper name={item.name} servings={servings} busy={busy} canAdd={!locked} onChange={onServings} />
      ) : (
        !locked && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onServings(1)}
            aria-label={`Ate this: ${item.name}`}
            className="flex shrink-0 items-center gap-1 rounded-full px-3 py-1.5 text-[13px] font-semibold text-brand ring-1 ring-brand/40 transition-colors hover:bg-brand-soft active:bg-brand-soft disabled:opacity-60"
          >
            <span aria-hidden="true" className="text-base leading-none">
              +
            </span>
            Ate this
          </button>
        )
      )}
    </li>
  )
}

// − 1.5 + : at the lowest step, − removes the dish. The number can also be typed: Enter or leaving the field
// saves it, Escape puts it back, and 0 removes the dish.
// canAdd false (a future date): the amount can only go down
function ServingStepper({ name, servings, busy, canAdd = true, onChange }) {
  const btn = 'grid h-7 w-7 place-items-center rounded-full text-lg leading-none font-semibold transition-colors disabled:opacity-40'
  const [draft, setDraft] = useState(null) // what is being typed; null when not editing
  const [invalid, setInvalid] = useState(false)
  // Escape blurs the field before React re-renders, so commit() would still see the typed draft
  const cancelled = useRef(false)

  const commit = () => {
    if (cancelled.current) {
      cancelled.current = false
      setDraft(null)
      return
    }
    if (draft === null) return
    const n = Math.round(Number(draft) * 100) / 100
    if (draft.trim() === '' || !Number.isFinite(n) || n < 0 || n > MAX_TYPED_SERVINGS) {
      setInvalid(true)
      setDraft(null)
      return
    }
    setDraft(null)
    setInvalid(false)
    if (n !== servings) onChange(n)
  }

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
      <label className="flex items-center text-sm font-bold text-brand-deep" title={invalid ? `Enter 0 to ${MAX_TYPED_SERVINGS}` : 'Type an amount'}>
        <input
          type="text"
          inputMode="decimal"
          value={draft ?? String(servings)}
          disabled={busy}
          onFocus={(e) => {
            setDraft(String(servings))
            setInvalid(false)
            e.target.select()
          }}
          onChange={(e) => {
            if (/^\d*\.?\d*$/.test(e.target.value)) setDraft(e.target.value)
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur()
            else if (e.key === 'Escape') {
              cancelled.current = true
              e.currentTarget.blur()
            }
          }}
          aria-label={`Servings of ${name}`}
          aria-invalid={invalid || undefined}
          className={`w-9 rounded-md bg-transparent text-right outline-none focus:bg-surface focus:ring-2 ${invalid ? 'ring-2 ring-bad/50' : 'focus:ring-brand/30'}`}
        />
        <span aria-hidden="true">×</span>
      </label>
      <button
        type="button"
        disabled={busy || !canAdd || servings >= MAX_SERVINGS}
        onClick={() => onChange(servings + SERVING_STEP)}
        aria-label={`More servings of ${name}`}
        className={`${btn} bg-brand text-white active:bg-brand-deep`}
      >
        +
      </button>
    </div>
  )
}

// Where this meal's budget comes from, in one sentence. The budget is a share of what the day has left after the
// other meals logged that day, so measuring it against the whole day ("Lunch gets 33% of today's 2000 kcal") read
// as a third of the day when it was half of what was left. `day` is "today" or "on Nov 12".
function budgetNote(target, day) {
  const daily = target.daily_target.kcal
  const budget = target.meal_budget.kcal
  if (!daily) return null
  // The day reached its target: remaining_day stops at 0, so what is left can't be worked out (or matter)
  if (target.remaining_day.kcal <= 0) return `You have reached ${day === 'today' ? "today's" : `the day's`} ${fmt(daily)} kcal.`
  // What the day had left for this meal and the ones still to come: the day minus the other meals logged
  const leftForRest = target.remaining_day.kcal + target.consumed_this_meal.kcal
  const pct = Math.round((100 * budget) / leftForRest)
  // Values come rounded to 0.1 kcal, so allow for that when asking whether other meals were logged
  if (leftForRest >= daily - 1) return `${Math.round((100 * budget) / daily)}% of your ${fmt(daily)} kcal day, shared with the meals still to come.`
  if (pct >= 100) return `All of the ${fmt(leftForRest)} kcal left after your other meals ${day}.`
  return `${pct}% of the ${fmt(leftForRest)} kcal left after your other meals ${day}; the rest is for the meals still to come.`
}

function MealTargetCard({ target, meal, day, onSetGoal }) {
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
      <ProgressRing value={eaten.kcal} max={budget.kcal} size={120} stroke={11} label={`${fmt(eaten.kcal)} of ${fmt(budget.kcal)} kcal logged for ${meal} ${day}, at any hall`}>
        <p className="text-2xl leading-none font-bold">{fmt(left.kcal)}</p>
        <p className="mt-1 text-[11px] font-medium text-muted">kcal left</p>
      </ProgressRing>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-brand">
          {mealLabel(meal)} budget: {fmt(budget.kcal)} kcal
        </p>
        <p className="mt-0.5 text-[13px] text-muted">{budgetNote(target, day)}</p>
        {/* consumed_this_meal counts this meal at every hall, so say so */}
        <p className="mt-1 text-sm text-muted">
          Logged for {meal} {day} (any hall): <span className="font-medium text-ink">{fmt(eaten.kcal)} kcal</span>
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

// logBlockedLabel: set for a future date, where the tray can't be logged yet (e.g. "Log on Nov 12")
function RecommendationCard({ rec, itemsById, logged, logBlockedLabel, logBusy, anotherBusy, noMore, onLog, onAnother }) {
  const lines = rec.items || []
  return (
    <Card tone="bg-ink" className="text-white">
      <p className="text-[13px] font-semibold text-brand">Recommended for you</p>
      {rec.error && <p className="mt-2 text-sm text-white/70">Couldn't load recommendations: {rec.error.message}</p>}
      {lines.length > 0 && (
        <ol className="mt-3 space-y-2">
          {lines.map((r, idx) => (
            <li key={r.item_id ?? r.name} className="flex items-center gap-3 rounded-xl bg-white/5 px-3 py-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[12px] font-bold">{idx + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{r.name}</p>
                <p className="text-[12px] text-white/60">
                  {amountOf(r, itemsById.get(r.item_id))} · {fmt(r.kcal)} kcal · {fmt(r.protein_g)}g protein
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {lines.length > 0 && (
        <p className="mt-3 text-sm text-white/70">
          Total <span className="font-semibold text-white">{fmt(rec.total.kcal)} kcal</span> · {fmt(rec.total.protein_g)}P {fmt(rec.total.carbs_g)}C{' '}
          {fmt(rec.total.fat_g)}F
        </p>
      )}
      {rec.note && <p className="mt-2 text-[13px] text-white/60">{rec.note}</p>}
      {noMore && <p className="mt-2 text-[13px] text-white/60">That's all the different plates I can build from this menu.</p>}
      {lines.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button onClick={onLog} disabled={logBusy || logged || Boolean(logBlockedLabel)} className="w-full !py-3">
            {logged ? 'Logged ✓' : logBlockedLabel || (logBusy ? 'Logging…' : 'Log this tray')}
          </Button>
          <Button onClick={onAnother} disabled={anotherBusy || logBusy} variant="soft" className="w-full !py-3">
            {anotherBusy ? 'Finding…' : 'Show me another'}
          </Button>
        </div>
      )}
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
