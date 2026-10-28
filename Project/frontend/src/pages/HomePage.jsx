import { useEffect, useState } from 'react'
import { getGoal, getGoalTimeline, getProgress } from '../api'
import { Bar, Button, Card, ErrorNote, Label, Loading, ProgressRing } from '../components/ui'
import { todayISO } from '../constants'
import { fmt, fmtDate } from '../format'

const STATUS = {
  on_track: ['On track', 'bg-good/10 text-good'],
  ahead: ['Ahead of plan', 'bg-good/10 text-good'],
  behind: ['Behind plan', 'bg-brand-soft text-brand-deep'],
  reached: ['Goal reached', 'bg-good/10 text-good'],
}

const GOAL_LABEL = { lose: 'Losing weight', maintain: 'Maintaining', gain: 'Gaining weight' }

// The meal coming up at this time of day
function nextMeal() {
  const hour = new Date().getHours()
  return hour < 10 ? 'breakfast' : hour < 15 ? 'lunch' : 'dinner'
}

function greeting() {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
}

async function loadHome(userId) {
  try {
    const [goal, progress, timeline] = await Promise.all([
      getGoal(userId),
      getProgress(userId, todayISO()),
      getGoalTimeline(userId).catch((err) => (err.status === 404 ? null : Promise.reject(err))),
    ])
    return { goal, progress, timeline }
  } catch (err) {
    if (err.status === 404) return { missingGoal: true }
    throw err
  }
}

export default function HomePage({ user, onNavigate }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    loadHome(user.id)
      .then((d) => !ignore && setData(d))
      .catch((err) => !ignore && setError(err))
    return () => {
      ignore = true
    }
  }, [user.id])

  const firstName = user.name.trim().split(/\s+/)[0]

  return (
    <section>
      <div className="mb-5">
        <p className="text-[13px] font-semibold text-brand">{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          {greeting()}, {firstName}
        </h1>
      </div>

      {error ? (
        <ErrorNote>{error.message}</ErrorNote>
      ) : !data ? (
        <Loading />
      ) : data.missingGoal ? (
        <Card>
          <p className="font-semibold">Set a goal to get started</p>
          <p className="mt-1 text-sm text-muted">We'll work out your daily calories and macros, then suggest dishes for each meal.</p>
          <Button onClick={() => onNavigate('/goal')} className="mt-4 w-full">
            Pick a goal
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          <TodayCard progress={data.progress} />
          <GoalCard timeline={data.timeline} goal={data.goal} onNavigate={onNavigate} />
        </div>
      )}

      <div className="mt-6">
        <Label className="mb-2 px-1">Quick actions</Label>
        <div className="grid grid-cols-1 gap-2">
          <Action title={`Plan ${nextMeal()}`} sub="See which dishes fit what you have left today" onClick={() => onNavigate('/plan')} primary />
          <Action title="Log your weight" sub="Keep your timeline up to date" onClick={() => onNavigate('/progress')} />
          <Action title="Change your goal" sub="Target weight, date and pace" onClick={() => onNavigate('/goal')} />
        </div>
      </div>
    </section>
  )
}

function TodayCard({ progress }) {
  const { target, actual, remaining, over } = progress
  const isOver = over.kcal > 0
  return (
    <Card>
      <div className="flex items-center gap-5">
        <ProgressRing value={actual.kcal} max={target.kcal} size={120} stroke={11} label={`${fmt(actual.kcal)} of ${fmt(target.kcal)} kcal eaten today`}>
          <p className={`text-2xl leading-none font-bold ${isOver ? 'text-bad' : ''}`}>{fmt(isOver ? over.kcal : remaining.kcal)}</p>
          <p className="mt-1 text-[11px] font-medium text-muted">{isOver ? 'kcal over' : 'kcal left'}</p>
        </ProgressRing>
        <div className="min-w-0 flex-1 space-y-2.5">
          <p className="text-[13px] font-semibold text-muted">
            Today: <span className="text-ink">{fmt(actual.kcal)}</span> / {fmt(target.kcal)} kcal
          </p>
          <Bar label="Protein" value={actual.protein_g} max={target.protein_g} unit="g" color="bg-ink" />
          <Bar label="Carbs" value={actual.carbs_g} max={target.carbs_g} unit="g" color="bg-brand" />
          <Bar label="Fat" value={actual.fat_g} max={target.fat_g} unit="g" color="bg-muted" />
        </div>
      </div>
    </Card>
  )
}

function GoalCard({ timeline, goal, onNavigate }) {
  if (!timeline) {
    return (
      <Card className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-muted">Your goal</p>
          <p className="mt-0.5 font-semibold">{GOAL_LABEL[goal?.goal_type] || 'Steady pace'}</p>
        </div>
        <button onClick={() => onNavigate('/goal')} className="text-sm font-semibold text-brand">
          Add a target date
        </button>
      </Card>
    )
  }
  const [label, tone] = STATUS[timeline.status] || STATUS.on_track
  const left = Math.abs(timeline.remaining_lbs)
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-muted">Your goal</p>
          <p className="mt-0.5 font-semibold">
            {timeline.target_weight_lbs} lb by {fmtDate(timeline.target_date)}
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[12px] font-semibold ${tone}`}>{label}</span>
      </div>
      <p className="mt-2 text-sm text-muted">
        {timeline.status === 'reached'
          ? `You're at ${timeline.latest_weight_lbs} lb. Nice work!`
          : `${timeline.latest_weight_lbs} lb now · ${left.toFixed(1)} lb to go`}
      </p>
      <button onClick={() => onNavigate('/progress')} className="mt-3 text-sm font-semibold text-brand">
        See your timeline
      </button>
    </Card>
  )
}

function Action({ title, sub, onClick, primary }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center justify-between rounded-2xl px-4 py-3.5 text-left transition-colors ${
        primary ? 'bg-brand text-white hover:bg-brand-deep' : 'bg-surface shadow-[0_1px_3px_rgba(19,41,75,0.06)] hover:bg-bg'
      }`}
    >
      <span>
        <span className="block font-semibold">{title}</span>
        <span className={`block text-[13px] ${primary ? 'text-white/80' : 'text-muted'}`}>{sub}</span>
      </span>
      <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m9 6 6 6-6 6" />
      </svg>
    </button>
  )
}
