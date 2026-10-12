import { useEffect, useState } from 'react'
import { getGoal, setGoal } from '../api'
import { Button, Card, ErrorNote, Label, PageHeader } from '../components/ui'
import { GOALS } from '../constants'
import { getPrefs, setPrefs } from '../session'

function suggestedGoal(user, targetWeight) {
  if (!targetWeight || !user.weight_lbs) return null
  const diff = targetWeight - user.weight_lbs
  return diff <= -2 ? 'lose' : diff >= 2 ? 'gain' : 'maintain'
}

export default function GoalPage({ user, onContinue }) {
  const prefs = getPrefs(user.id)
  const [goalType, setGoalType] = useState(prefs.goalType || null)
  const [goal, setGoalData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null)
  const suggestion = suggestedGoal(user, prefs.targetWeight)

  // Show the saved targets if a goal was set before (404 just means not yet)
  useEffect(() => {
    getGoal(user.id)
      .then(setGoalData)
      .catch((err) => err.status !== 404 && setError(err.message))
  }, [user.id])

  const choose = async (type) => {
    setBusy(type)
    setError('')
    try {
      const result = await setGoal(user.id, type)
      setGoalData(result)
      setGoalType(type)
      setPrefs(user.id, { goalType: type })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section>
      <PageHeader title="Your goal" sub="Your height, weight, age, sex and activity set your daily calorie and macro targets." />

      {suggestion && !goalType && (
        <Card tone="bg-brand-soft" className="mb-4 text-sm">
          Your target weight is {prefs.targetWeight} lb and you weigh {user.weight_lbs} lb, so{' '}
          <span className="font-semibold">{GOALS[suggestion].label.toLowerCase()}</span> fits best.
        </Card>
      )}

      <div className="space-y-3">
        {Object.keys(GOALS).map((g) => {
          const selected = goalType === g
          return (
            <button
              key={g}
              onClick={() => choose(g)}
              disabled={busy !== null}
              aria-pressed={selected}
              className={`flex w-full items-center gap-4 rounded-2xl bg-surface p-4 text-left shadow-[0_1px_3px_rgba(19,41,75,0.06)] ring-2 transition disabled:cursor-wait ${
                selected ? 'ring-brand' : 'ring-transparent hover:ring-line'
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-[17px] font-semibold">
                  {GOALS[g].label}
                  {suggestion === g && !selected && <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-semibold text-brand-deep">Suggested</span>}
                </p>
                <p className="mt-0.5 text-sm text-muted">{busy === g ? 'Saving…' : GOALS[g].note}</p>
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

      <div className="mt-4 space-y-3">
        <ErrorNote>{error}</ErrorNote>
        {goal?.warning && <ErrorNote>{goal.warning}</ErrorNote>}
      </div>

      {goal && (
        <div className="mt-6">
          <Label className="mb-2">Your daily targets</Label>
          <div className="grid grid-cols-2 gap-3">
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
          <Button onClick={onContinue} variant="dark" className="mt-5 w-full">
            Plan my next meal
          </Button>
        </div>
      )}
    </section>
  )
}
