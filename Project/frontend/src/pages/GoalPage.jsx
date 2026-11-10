import { useEffect, useState } from 'react'
import { getGoal, getUser, previewGoal, setGoal, setMeals } from '../api'
import { Button, Card, ErrorNote, Field, Input, Label, PageHeader } from '../components/ui'
import { GOALS, MEAL_GROUPS, MEAL_WEIGHTS } from '../constants'
import { fmtDate, isoInDays, mealLabel } from '../format'

// Quick picks for the target date: [label, days from today]
const DATE_PICKS = [
  ['4 weeks', 28],
  ['8 weeks', 56],
  ['12 weeks', 84],
  ['6 months', 182],
]

const TIERS = {
  healthy: ['Healthy pace', 'bg-good/10 text-good'],
  aggressive: ['Fast but allowed', 'bg-brand-soft text-brand-deep'],
  unsafe: ['Not safe', 'bg-bad/10 text-bad'],
}

export default function GoalPage({ user, onUserChange, onContinue }) {
  const [goal, setGoalData] = useState(null)
  const [type, setType] = useState(null)
  const [targetWeight, setTargetWeight] = useState('')
  const [targetDate, setTargetDate] = useState(isoInDays(56))
  const [preview, setPreview] = useState({ key: null })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Weigh-ins on the Progress page change the current weight, so ask the server rather than trust the login copy
  const [profile, setProfile] = useState(user)
  const currentWeight = profile.weight_lbs

  useEffect(() => {
    getUser(user.id)
      .then(setProfile)
      .catch(() => {})
  }, [user.id])

  // Saved meals: keep this page and the rest of the app (Plan and Home pick the default meal from them) up to date
  const mealsSaved = (u) => {
    setProfile(u)
    onUserChange(u)
  }

  // Show the saved goal if there is one (404 just means not yet)
  useEffect(() => {
    getGoal(user.id)
      .then((g) => {
        setGoalData(g)
        setType(g.goal_type)
        if (g.target_date) {
          setTargetWeight(String(g.target_weight_lbs))
          setTargetDate(g.target_date)
        }
      })
      .catch((err) => err.status !== 404 && setError(err.message))
  }, [user.id])

  const weight = Number(targetWeight)
  const timelineType = type === 'lose' || type === 'gain'
  // The target has to point the way the chosen goal does
  const mismatch =
    timelineType && weight > 0 && (type === 'lose' ? weight >= currentWeight : weight <= currentWeight)
  const canPreview = timelineType && weight >= 50 && weight <= 700 && targetDate && !mismatch
  const previewKey = canPreview ? `${weight}|${targetDate}` : null

  // Check the plan as the user types (debounced), so unsafe requests are caught before saving
  useEffect(() => {
    if (!previewKey) return
    let ignore = false
    const timer = setTimeout(() => {
      previewGoal(user.id, weight, targetDate)
        .then((plan) => !ignore && setPreview({ key: previewKey, plan }))
        .catch((err) => !ignore && setPreview({ key: previewKey, error: err.message }))
    }, 400)
    return () => {
      ignore = true
      clearTimeout(timer)
    }
  }, [previewKey, user.id, weight, targetDate])
  const current = previewKey && preview.key === previewKey ? preview : null
  const plan = current?.plan

  const save = async (body) => {
    setBusy(true)
    setError('')
    try {
      setGoalData(await setGoal(user.id, body))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const choose = (g) => {
    setType(g)
    // Nothing to replace (no goal yet, or already maintaining): save at once. Switching from a lose or gain goal
    // asks first (the card below), since it replaces that goal and its timeline.
    if (g === 'maintain' && (!goal || goal.goal_type === 'maintain')) save({ goal_type: 'maintain' })
  }

  const isSaved =
    goal &&
    goal.goal_type === type &&
    (timelineType ? goal.target_date === targetDate && goal.target_weight_lbs === weight : !goal.target_date)
  const confirmMaintain = type === 'maintain' && goal && goal.goal_type !== 'maintain'
  // Another goal is being picked or edited above, so the saved targets below aren't what it will give
  const outdated = goal && !isSaved && (type !== goal.goal_type || targetWeight !== '')

  return (
    <section>
      <PageHeader title="Your goal" sub="Your height, weight, age, sex and activity set your daily calorie and macro targets." />

      <div className="space-y-3">
        {Object.keys(GOALS).map((g) => {
          const selected = type === g
          return (
            <button
              key={g}
              onClick={() => choose(g)}
              disabled={busy}
              aria-pressed={selected}
              className={`flex w-full items-center gap-4 rounded-2xl bg-surface p-4 text-left shadow-[0_1px_3px_rgba(19,41,75,0.06)] ring-2 transition disabled:cursor-wait ${
                selected ? 'ring-brand' : 'ring-transparent hover:ring-line'
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="text-[17px] font-semibold">{GOALS[g].label}</p>
                <p className="mt-0.5 text-sm text-muted">{GOALS[g].note}</p>
              </div>
              <span
                aria-hidden="true"
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 ${selected ? 'border-brand bg-brand text-white' : 'border-line'}`}
              >
                {selected && (
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m5 12 5 5 9-10" />
                  </svg>
                )}
              </span>
            </button>
          )
        })}
      </div>

      {timelineType && (
        <Card className="mt-4">
          <h2 className="text-lg font-bold">Your timeline</h2>
          <p className="mt-1 text-sm text-muted">You weigh {currentWeight} lb now.</p>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <Field label="Target weight (lb)">
              <Input
                type="number"
                inputMode="decimal"
                min="50"
                max="700"
                step="0.5"
                value={targetWeight}
                onChange={(e) => setTargetWeight(e.target.value)}
              />
            </Field>
            <Field label="Reach it by">
              <Input type="date" min={isoInDays(1)} max={isoInDays(730)} value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </Field>
          </div>
          <div className="no-scrollbar -mx-1 mt-3 flex gap-2 overflow-x-auto px-1">
            {DATE_PICKS.map(([label, days]) => (
              <button
                key={label}
                type="button"
                onClick={() => setTargetDate(isoInDays(days))}
                className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition-colors ${
                  targetDate === isoInDays(days) ? 'bg-ink text-white ring-ink' : 'bg-surface ring-line hover:bg-bg'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {mismatch && (
            <p className="mt-4 text-sm text-muted">
              To {type === 'lose' ? 'lose weight' : 'gain'}, the target has to be {type === 'lose' ? 'below' : 'above'} {currentWeight} lb.
            </p>
          )}
          {current?.error && (
            <div className="mt-4">
              <ErrorNote>{current.error}</ErrorNote>
            </div>
          )}
          {plan && <PlanPreview plan={plan} onUseDate={setTargetDate} onUseWeight={(w) => setTargetWeight(String(w))} />}

          <Button
            onClick={() => save({ target_weight_lbs: weight, target_date: targetDate })}
            disabled={busy || !plan || plan.tier === 'unsafe' || isSaved}
            className="mt-5 w-full"
          >
            {busy ? 'Saving…' : isSaved ? 'Plan saved' : 'Save this plan'}
          </Button>
          <button
            type="button"
            onClick={() => save({ goal_type: type })}
            disabled={busy}
            className="mt-3 w-full text-center text-sm font-medium text-muted hover:text-ink"
          >
            No end date: use a steady pace instead
          </button>
        </Card>
      )}

      {confirmMaintain && (
        <Card className="mt-4">
          <h2 className="text-lg font-bold">Switch to maintaining?</h2>
          <p className="mt-1 text-sm text-muted">
            This replaces your current goal (<span className="font-medium text-ink">{goalSummary(goal)}</span>) with eating what your body uses.
          </p>
          <Button onClick={() => save({ goal_type: 'maintain' })} disabled={busy} className="mt-4 w-full">
            {busy ? 'Saving…' : 'Switch to maintain'}
          </Button>
          <button
            type="button"
            onClick={() => setType(goal.goal_type)}
            disabled={busy}
            className="mt-3 w-full text-center text-sm font-medium text-muted hover:text-ink"
          >
            Keep my current goal
          </button>
        </Card>
      )}

      <div className="mt-4 space-y-3">
        <ErrorNote>{error}</ErrorNote>
        {goal?.warning && <ErrorNote>{goal.warning}</ErrorNote>}
      </div>

      {goal && (
        <div className="mt-6">
          <Label className="mb-2">{outdated ? 'Your current targets' : 'Your daily targets'}</Label>
          {outdated && (
            <p role="status" className="mb-3 rounded-xl bg-brand-soft px-3.5 py-2.5 text-sm text-brand-deep">
              These are from your saved goal ({goalSummary(goal)}). They change once you save the new goal above.
            </p>
          )}
          {goal.target_date && (
            <p className="mb-3 text-sm">
              Reach <span className="font-semibold">{goal.target_weight_lbs} lb</span> by{' '}
              <span className="font-semibold">{fmtDate(goal.target_date)}</span>: about {goal.weekly_rate_lbs} lb a week.
            </p>
          )}
          <div className={`grid grid-cols-2 gap-3 transition-opacity ${outdated ? 'opacity-50' : ''}`}>
            {[
              ['Calories', goal.calorie_goal, 'kcal', true],
              ['Protein', goal.protein_goal_g, 'g'],
              ['Carbs', goal.carb_goal_g, 'g'],
              ['Fat', goal.fat_goal_g, 'g'],
            ].map(([label, value, unit, hi]) => (
              <Card key={label} tone={hi ? 'bg-brand' : undefined} className={hi ? 'text-white' : ''}>
                <p className={`text-[13px] font-semibold ${hi ? 'text-white/80' : 'text-muted'}`}>{label}</p>
                <p className="mt-2 text-3xl leading-none font-bold tracking-tight">
                  {value ?? '—'}
                  <span className={`ml-1 text-sm font-medium ${hi ? 'text-white/80' : 'text-muted'}`}>{unit}</span>
                </p>
              </Card>
            ))}
          </div>
          <MealsCard userId={user.id} meals={profile.meals} calorieGoal={goal.calorie_goal} onSaved={mealsSaved} />
          <Button onClick={onContinue} variant="dark" className="mt-5 w-full">
            Plan my next meal
          </Button>
        </div>
      )}

      <p className="mt-6 text-center text-[12px] text-muted">
        Estimates based on standard formulas, not medical advice. Talk to a doctor or dietitian before a big change.
      </p>
    </section>
  )
}

// The saved goal in a few words: "Lose weight, 150 lb by Dec 1", "Gain muscle at a steady pace", "Maintain"
function goalSummary(goal) {
  const label = GOALS[goal.goal_type]?.label || goal.goal_type
  if (goal.target_date) return `${label}, ${goal.target_weight_lbs} lb by ${fmtDate(goal.target_date)}`
  return goal.goal_type === 'maintain' ? label : `${label} at a steady pace`
}

// What the plan needs, how safe it is, and, if it isn't, one-tap safe alternatives
function PlanPreview({ plan, onUseDate, onUseWeight }) {
  const [tierLabel, tierClass] = TIERS[plan.tier]
  const alt = plan.alternatives
  const change = plan.daily_calorie_change
  return (
    <div className="mt-4 rounded-xl bg-bg p-4">
      <div className="flex items-center justify-between gap-3">
        <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${tierClass}`}>{tierLabel}</span>
        <span className="text-sm text-muted">{plan.weekly_rate_lbs} lb a week</span>
      </div>
      <p className="mt-3 text-2xl font-bold tracking-tight">
        {plan.calorie_goal} <span className="text-sm font-medium text-muted">kcal a day</span>
      </p>
      {change !== 0 && (
        <p className="text-sm text-muted">
          {Math.abs(change)} kcal {change < 0 ? 'under' : 'over'} what you burn
        </p>
      )}

      {plan.tier === 'unsafe' && (
        <>
          <ul className="mt-3 space-y-1.5 text-sm text-bad">
            {plan.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
          {alt && (alt.earliest_date || alt.target_weight_by_date) && (
            <div className="mt-4 space-y-2">
              <Label>Try a safe plan instead</Label>
              {alt.recommended_date && (
                <AltButton
                  onClick={() => {
                    onUseWeight(alt.target_weight_lbs)
                    onUseDate(alt.recommended_date)
                  }}
                >
                  {alt.target_weight_lbs} lb by {fmtDate(alt.recommended_date)} <span className="text-muted">(steady pace)</span>
                </AltButton>
              )}
              {alt.earliest_date && alt.earliest_date !== alt.recommended_date && (
                <AltButton
                  onClick={() => {
                    onUseWeight(alt.target_weight_lbs)
                    onUseDate(alt.earliest_date)
                  }}
                >
                  {alt.target_weight_lbs} lb by {fmtDate(alt.earliest_date)} <span className="text-muted">(fastest safe)</span>
                </AltButton>
              )}
              {alt.target_weight_by_date && (
                <AltButton onClick={() => onUseWeight(alt.target_weight_by_date)}>
                  {alt.target_weight_by_date} lb by {fmtDate(plan.target_date)} <span className="text-muted">(keep your date)</span>
                </AltButton>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Which meals the user eats each day. Tapping one saves at once (PUT /users/{id}/meals); at least one stays on.
// The day's calories are shared between the chosen meals, shown as a share and kcal for each.
function MealsCard({ userId, meals, calorieGoal, onSaved }) {
  const chosen = meals?.length ? meals : MEAL_GROUPS // null from the backend means all three
  const [saving, setSaving] = useState(null) // the meal being toggled
  const [error, setError] = useState('')

  const toggle = async (meal) => {
    const next = MEAL_GROUPS.filter((m) => (m === meal ? !chosen.includes(m) : chosen.includes(m)))
    setSaving(meal)
    setError('')
    try {
      // All three is the backend's default, so send null rather than the full list
      onSaved(await setMeals(userId, next.length === MEAL_GROUPS.length ? null : next))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(null)
    }
  }

  const total = chosen.reduce((sum, m) => sum + MEAL_WEIGHTS[m], 0)
  return (
    <Card className="mt-3">
      <h2 className="text-lg font-bold">Meals you eat</h2>
      <p className="mt-1 text-sm text-muted">Your daily calories are split between these. Skip one and the others get bigger.</p>
      <div role="group" aria-label="Meals you eat" className="mt-4 grid grid-cols-3 gap-2">
        {MEAL_GROUPS.map((m) => {
          const on = chosen.includes(m)
          const last = on && chosen.length === 1
          return (
            <button
              key={m}
              type="button"
              onClick={() => toggle(m)}
              disabled={saving !== null || last}
              aria-pressed={on}
              title={last ? 'Keep at least one meal' : undefined}
              className={`rounded-xl px-2 py-3 text-center ring-2 transition disabled:cursor-not-allowed ${
                on ? 'bg-brand-soft ring-brand' : 'bg-bg text-muted ring-transparent hover:ring-line'
              } ${saving === m ? 'opacity-60' : ''}`}
            >
              <span className="block text-[15px] font-semibold">{mealLabel(m)}</span>
              <span className="mt-0.5 block text-[12px]">
                {on ? `${Math.round((100 * MEAL_WEIGHTS[m]) / total)}% · ${Math.round((calorieGoal * MEAL_WEIGHTS[m]) / total).toLocaleString()} kcal` : 'Skipped'}
              </span>
            </button>
          )
        })}
      </div>
      {chosen.length === 1 && <p className="mt-2 text-[13px] text-muted">One meal a day gets all of your calories. Keep at least one meal.</p>}
      <div className="mt-3">
        <ErrorNote>{error}</ErrorNote>
      </div>
    </Card>
  )
}

function AltButton({ onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-xl bg-surface px-3.5 py-3 text-left text-sm font-medium ring-1 ring-line transition-colors hover:ring-brand"
    >
      <span>{children}</span>
      <span className="font-semibold text-brand">Use</span>
    </button>
  )
}
