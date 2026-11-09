import { useId, useRef, useState } from 'react'
import { quickAddFood } from '../api'
import { Button, ErrorNote, Field, Input, Segmented } from './ui'

// The meals a quick add can count toward. A snack comes off the day without using up a meal; logging something as
// "lunch" counts as having had lunch, so the rest of the day moves on to dinner (see POST /food-logs in Docs/API.md).
const MEALS = [
  ['breakfast', 'Breakfast'],
  ['lunch', 'Lunch'],
  ['dinner', 'Dinner'],
  ['snack', 'Snack'],
]

// Highest values the API accepts (FoodLogCreate in app/models.py)
const LIMITS = { kcal: 5000, protein_g: 500, carbs_g: 1000, fat_g: 500 }
const MACROS = [
  ['protein_g', 'Protein'],
  ['carbs_g', 'Carbs'],
  ['fat_g', 'Fat'],
]

const emptyForm = (meal) => ({ name: '', kcal: '', protein_g: '', carbs_g: '', fat_g: '', meal })

// "+ Add food": a button that opens a small form for food that isn't on a dining hall menu, logged on `date`.
// `onAdded(log)` runs after it is saved, so the page can reload its numbers.
export default function QuickAddButton({ userId, date, defaultMeal = 'snack', onAdded, className = '', children = '+ Add food' }) {
  const dialog = useRef(null)
  const titleId = useId() // a page can have more than one of these
  const [form, setForm] = useState(() => emptyForm(defaultMeal))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const open = () => {
    setForm(emptyForm(defaultMeal))
    setError('')
    dialog.current.showModal()
  }
  const close = () => dialog.current.close()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const kcal = Number(form.kcal)
    if (!form.name.trim()) return setError('What did you eat?')
    if (!(kcal > 0 && kcal <= LIMITS.kcal)) return setError(`Calories must be between 1 and ${LIMITS.kcal.toLocaleString()}.`)
    const food = { name: form.name.trim(), kcal, meal: form.meal, date }
    for (const [key, label] of MACROS) {
      if (form[key] === '') continue // optional: left out counts as 0
      const grams = Number(form[key])
      if (!(grams >= 0 && grams <= LIMITS[key])) return setError(`${label} must be between 0 and ${LIMITS[key]} g.`)
      food[key] = grams
    }
    setBusy(true)
    try {
      const log = await quickAddFood(userId, food)
      close()
      onAdded(log)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" onClick={open} className={className || 'text-sm font-semibold text-brand'}>
        {children}
      </button>
      {/* A native modal dialog: it keeps focus inside, and Escape closes it. A tap on the backdrop closes it too. */}
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        onClick={(e) => e.target === dialog.current && close()}
        className="m-auto w-[min(28rem,calc(100%-2rem))] rounded-2xl bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/40"
      >
        <form onSubmit={submit} className="space-y-4 p-5">
          <div>
            <h2 id={titleId} className="text-lg font-bold">
              Add food
            </h2>
            <p className="mt-1 text-sm text-muted">Something that isn't on a dining hall menu: a snack, a drink, a meal off campus.</p>
          </div>

          <Field label="What did you eat?">
            <Input required autoFocus maxLength={100} value={form.name} onChange={set('name')} placeholder="e.g. Chipotle bowl" />
          </Field>
          <Field label="Calories" hint="The package or the restaurant's website usually lists them.">
            <Input required type="number" inputMode="numeric" min="1" max={LIMITS.kcal} step="1" value={form.kcal} onChange={set('kcal')} />
          </Field>

          <div>
            <p className="text-[13px] font-semibold text-muted">
              Protein, carbs, fat <span className="font-normal">(optional, g)</span>
            </p>
            <div className="mt-1.5 grid grid-cols-3 gap-2">
              {MACROS.map(([key, label]) => (
                <Input
                  key={key}
                  type="number"
                  inputMode="decimal"
                  min="0"
                  max={LIMITS[key]}
                  step="any"
                  value={form[key]}
                  onChange={set(key)}
                  placeholder={label}
                  aria-label={`${label}, grams`}
                />
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-[13px] font-semibold text-muted">Counts toward</p>
            <Segmented options={MEALS} value={form.meal} onChange={(meal) => setForm((f) => ({ ...f, meal }))} />
            <p className="mt-1.5 text-[12px] text-muted">
              {form.meal === 'snack'
                ? "Comes off the day's calories without using up a meal."
                : `Counts as your ${form.meal}, so the rest of the day goes to your other meals.`}
            </p>
          </div>

          <ErrorNote>{error}</ErrorNote>

          <div className="grid grid-cols-2 gap-2">
            <Button type="button" variant="soft" onClick={close} disabled={busy}>
              Cancel
            </Button>
            <Button disabled={busy}>{busy ? 'Adding…' : 'Add'}</Button>
          </div>
        </form>
      </dialog>
    </>
  )
}
