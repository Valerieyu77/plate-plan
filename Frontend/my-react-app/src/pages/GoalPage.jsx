import { useEffect, useState } from 'react'
import { getGoal, setGoal } from '../api'
import { ErrorNote, SectionHead } from '../components/ui'
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
    <section className="pt-10 pb-24">
      <SectionHead
        n="01"
        title="Pick your goal"
        sub="We use your height, weight, age, sex and activity level to set daily calorie and macro targets."
      />

      {suggestion && !goalType && (
        <p className="mb-6 text-ink-soft">
          Your target weight is {prefs.targetWeight} lb and you weigh {user.weight_lbs} lb, so{' '}
          <span className="font-medium text-ink">{GOALS[suggestion].label.toLowerCase()}</span> fits best.
        </p>
      )}

      <div className="grid gap-px border border-ink bg-ink md:grid-cols-3">
        {Object.keys(GOALS).map((g) => {
          const selected = goalType === g
          return (
            <button
              key={g}
              onClick={() => choose(g)}
              disabled={busy !== null}
              aria-pressed={selected}
              className={`p-6 text-left transition-colors disabled:cursor-wait ${selected ? 'bg-ink text-paper' : 'bg-paper hover:bg-paper-deep'}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-serif text-2xl font-medium">{GOALS[g].label}</span>
                <span className={`font-mono text-[11px] uppercase tracking-wider ${selected ? 'text-illini' : 'text-ink-soft'}`}>
                  {busy === g ? 'Saving…' : selected ? '● Your goal' : suggestion === g ? 'Suggested' : 'Select'}
                </span>
              </div>
              <p className={`mt-1 text-sm ${selected ? 'text-paper/70' : 'text-ink-soft'}`}>{GOALS[g].note}</p>
            </button>
          )
        })}
      </div>

      <div className="mt-6 space-y-4">
        <ErrorNote>{error}</ErrorNote>
        {goal?.warning && <ErrorNote>{goal.warning}</ErrorNote>}
      </div>

      {goal && (
        <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <p className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">Your daily targets</p>
            <div className="mt-4 grid grid-cols-2 gap-px border border-ink bg-ink sm:grid-cols-4">
              {[
                ['Calories', goal.calorie_goal, 'kcal', true],
                ['Protein', goal.protein_goal_g, 'g'],
                ['Carbs', goal.carb_goal_g, 'g'],
                ['Fat', goal.fat_goal_g, 'g'],
              ].map(([label, value, unit, hi]) => (
                <div key={label} className={`p-5 ${hi ? 'bg-illini text-white' : 'bg-paper'}`}>
                  <p className={`font-mono text-[12px] uppercase tracking-wider ${hi ? 'text-white/80' : 'text-ink-soft'}`}>{label}</p>
                  <p className="mt-4 font-serif text-5xl leading-none font-medium">
                    {value ?? '—'}
                    <span className="ml-1 font-mono text-base">{unit}</span>
                  </p>
                </div>
              ))}
            </div>
          </div>
          <button onClick={onContinue} className="bg-ink px-6 py-3.5 text-[15px] font-medium text-paper transition-colors hover:bg-illini">
            Plan my next meal →
          </button>
        </div>
      )}
    </section>
  )
}
