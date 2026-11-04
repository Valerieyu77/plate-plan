import { useEffect, useState } from 'react'
import { getEvents, getGoal, getGoalTimeline, getProgress } from '../api'
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

      <EventsList />
    </section>
  )
}

const CALENDAR_PAGE = 'https://calendars.illinois.edu/list/637'
const MAX_EVENTS = 6

// "Wed, Nov 4 · 11:15 AM – 12:45 PM" (event times are campus local time, no zone)
function eventTime(e) {
  const start = new Date(e.start)
  const day = start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  if (e.all_day) return `${day} · All day`
  const time = (d) => d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  return e.end ? `${day} · ${time(start)} – ${time(new Date(e.end))}` : `${day} · ${time(start)}`
}

// Upcoming exercise events from the campus Recreation calendar (skating, classes, runs...)
function EventsList() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    getEvents()
      .then((d) => !ignore && setData(d))
      .catch((err) => !ignore && setError(err))
    return () => {
      ignore = true
    }
  }, [])

  // The list starts at the beginning of today, so drop what has already ended
  const now = new Date()
  const upcoming = (data?.events || []).filter((e) => new Date(e.end || e.start) > now || e.all_day).slice(0, MAX_EVENTS)

  return (
    <div className="mt-6">
      <div className="mb-2 flex items-baseline justify-between px-1">
        <Label>Campus fitness events</Label>
        <a href={data?.source || CALENDAR_PAGE} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-brand">
          Full calendar
        </a>
      </div>
      <Card className="!p-0">
        {error ? (
          <p className="p-5 text-sm text-muted">Couldn't load campus events. {error.message}</p>
        ) : !data ? (
          <div className="px-5">
            <Loading>Loading events…</Loading>
          </div>
        ) : upcoming.length === 0 ? (
          <p className="p-5 text-sm text-muted">No fitness events in the next week.</p>
        ) : (
          <ul className="divide-y divide-line">
            {upcoming.map((e) => (
              <li key={e.url || `${e.title}-${e.start}`}>
                <a href={e.url || CALENDAR_PAGE} target="_blank" rel="noopener noreferrer" className="block px-5 py-3.5 transition-colors hover:bg-bg">
                  <span className="block font-semibold">{e.title}</span>
                  <span className="mt-0.5 block text-[13px] font-medium text-brand">{eventTime(e)}</span>
                  {e.location && <span className="mt-0.5 block text-[13px] text-muted">{e.location}</span>}
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
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
