import { useEffect, useState } from 'react'
import { addWorkoutLog, deleteWorkoutLog, getWorkout, getWorkoutLogs } from '../api'
import { Button, Card, ChipScroller, ErrorNote, Label, Loading, PageHeader, Segmented } from '../components/ui'
import { INTENSITIES, MUSCLE_GROUPS, todayISO } from '../constants'
import { fmt } from '../format'
import { getPrefs, setPrefs } from '../session'

// 0 = let the backend pick the length for the intensity (20 / 35 / 50 min)
const DURATIONS = [0, 15, 20, 30, 45, 60]
const DEFAULT_FILTERS = { muscles: [], minutes: 0, intensity: 'moderate', noEquipment: false }
const KIND_LABEL = { cardio: 'Cardio', strength: 'Strength', mobility: 'Stretch' }
const MUSCLE_LABEL = Object.fromEntries(MUSCLE_GROUPS.map((m) => [m.value, m.label]))

// Filters -> GET /users/{id}/workout options. Picking only muscles means strength on them, so
// cardio ("heart") together with muscles asks for a mixed session.
function workoutQuery(filters) {
  const { muscles, minutes, intensity, noEquipment } = filters
  const focus = muscles.includes('heart') && muscles.length > 1 ? 'mixed' : undefined
  return { muscles, focus, intensity, noEquipment, minutes: minutes || undefined }
}

// "3 × 10" for strength, "20 min" for everything timed
const dose = (e) => (e.sets ? `${e.sets} × ${e.reps}` : `${e.minutes} min`)

export default function WorkoutPage({ user }) {
  const today = todayISO()
  const [filters, setFilters] = useState(() => ({ ...DEFAULT_FILTERS, ...getPrefs(user.id).workout }))
  // {key, data, exercises, swapped} or {key, error}. `exercises` is the plan with swaps applied;
  // `swapped` the ids swapped out, so Swap doesn't bring them back.
  const [plan, setPlan] = useState(null)
  const [logs, setLogs] = useState({ list: [] })
  const [expanded, setExpanded] = useState(() => new Set())
  const [swapping, setSwapping] = useState(null) // index of the exercise being swapped
  const [logBusy, setLogBusy] = useState(null) // id of the exercise being logged or un-logged
  const [notice, setNotice] = useState(null) // {index, text, error} under one exercise

  const query = workoutQuery(filters)
  const planKey = JSON.stringify(query)

  useEffect(() => {
    let ignore = false
    getWorkout(user.id, { date: today, ...JSON.parse(planKey) })
      .then((data) => !ignore && setPlan({ key: planKey, data, exercises: data.exercises, swapped: [] }))
      .catch((error) => !ignore && setPlan({ key: planKey, error }))
    return () => {
      ignore = true
    }
  }, [user.id, today, planKey])

  // Today's logs, to show which exercises are already done
  useEffect(() => {
    let ignore = false
    getWorkoutLogs(user.id, today)
      .then((list) => !ignore && setLogs({ list }))
      .catch((error) => !ignore && setLogs({ list: [], error }))
    return () => {
      ignore = true
    }
  }, [user.id, today])

  const updateFilters = (patch) => {
    const next = { ...filters, ...patch }
    setFilters(next)
    setPrefs(user.id, { workout: next })
    setNotice(null)
  }

  const toggleMuscle = (m) =>
    updateFilters({ muscles: filters.muscles.includes(m) ? filters.muscles.filter((x) => x !== m) : [...filters.muscles, m] })

  const toggleExpanded = (id) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const loaded = plan?.key === planKey ? plan : null
  const exercises = loaded?.exercises || []
  const logFor = (id) => logs.list.find((l) => l.exercise_id === id)

  const swap = async (index) => {
    const current = exercises[index]
    setSwapping(index)
    setNotice(null)
    try {
      const avoid = [...new Set([...loaded.swapped, ...exercises.map((e) => e.id)])]
      const next = await getWorkout(user.id, { date: today, ...query, avoid })
      // Avoiding moves reshuffles the whole plan, and a new move can land in another slot, so take
      // only one replacement: this slot's if it fits, else any new move that could stand in for this one
      const fits = (e) =>
        e.kind === current.kind &&
        !exercises.some((x) => x.id === e.id) &&
        (e.kind === 'strength' ? e.muscles[0] === current.muscles[0] : e.minutes === current.minutes)
      const pick = [next.exercises[index], ...next.exercises].find((e) => e && fits(e))
      if (!pick) {
        const what = current.kind === 'strength' ? MUSCLE_LABEL[current.muscles[0]]?.toLowerCase() : KIND_LABEL[current.kind]?.toLowerCase()
        setNotice({ index, text: `No other ${what || ''} move fits these filters.` })
      } else {
        setPlan((p) =>
          p.key === planKey
            ? { ...p, exercises: p.exercises.map((e, i) => (i === index ? pick : e)), swapped: [...p.swapped, current.id] }
            : p,
        )
      }
    } catch (err) {
      setNotice({ index, text: err.message, error: true })
    } finally {
      setSwapping(null)
    }
  }

  const complete = async (index) => {
    const e = exercises[index]
    setLogBusy(e.id)
    setNotice(null)
    try {
      // Send the card's kcal so the log matches what was shown (warm-ups and stretches are done light)
      const log = await addWorkoutLog(user.id, {
        exercise_id: e.id,
        minutes: e.minutes,
        intensity: loaded.data.intensity,
        kcal: e.kcal ?? undefined,
        date: today,
      })
      setLogs((l) => ({ ...l, list: [...l.list, log] }))
    } catch (err) {
      setNotice({ index, text: err.message, error: true })
    } finally {
      setLogBusy(null)
    }
  }

  const undo = async (index) => {
    const e = exercises[index]
    const log = logFor(e.id)
    setLogBusy(e.id)
    setNotice(null)
    try {
      await deleteWorkoutLog(user.id, log.id)
      setLogs((l) => ({ ...l, list: l.list.filter((x) => x.id !== log.id) }))
    } catch (err) {
      setNotice({ index, text: err.message, error: true })
    } finally {
      setLogBusy(null)
    }
  }

  const totalMinutes = exercises.reduce((sum, e) => sum + e.minutes, 0)
  const totalKcal = exercises.every((e) => e.kcal != null) ? exercises.reduce((sum, e) => sum + e.kcal, 0) : null
  const doneCount = exercises.filter((e) => logFor(e.id)).length

  return (
    <section>
      <PageHeader
        title="Workout"
        sub={
          loaded?.data
            ? `Today · ${fmt(totalMinutes)} min${totalKcal != null ? ` · about ${fmt(totalKcal)} kcal` : ''}`
            : 'A plan for today, from your goal and the filters below'
        }
      />

      <div className="space-y-4">
        <div>
          <Label className="mb-2 px-1">Body part</Label>
          <div role="group" aria-label="Body part" className="no-scrollbar -mx-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1">
            <Chip active={filters.muscles.length === 0} onClick={() => updateFilters({ muscles: [] })}>
              Any
            </Chip>
            {MUSCLE_GROUPS.map((m) => (
              <Chip key={m.value} active={filters.muscles.includes(m.value)} onClick={() => toggleMuscle(m.value)}>
                {m.label}
              </Chip>
            ))}
          </div>
        </div>

        <div>
          <Label className="mb-2 px-1">Duration</Label>
          <ChipScroller
            label="Duration"
            options={DURATIONS}
            value={filters.minutes}
            onChange={(minutes) => updateFilters({ minutes })}
            getLabel={(m) => (m ? `${m} min` : 'Suggested')}
          />
        </div>

        <div>
          <Label className="mb-2 px-1">Intensity</Label>
          <Segmented options={INTENSITIES} value={filters.intensity} onChange={(intensity) => updateFilters({ intensity })} />
        </div>

        <label className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3.5 shadow-[0_1px_3px_rgba(19,41,75,0.06)]">
          <span>
            <span className="block font-semibold">No equipment required</span>
            <span className="block text-[13px] text-muted">Bodyweight moves you can do anywhere</span>
          </span>
          <input
            type="checkbox"
            checked={filters.noEquipment}
            onChange={(e) => updateFilters({ noEquipment: e.target.checked })}
            className="h-5 w-5 shrink-0 accent-[var(--color-brand)]"
          />
        </label>
      </div>

      <div className="mt-6">
        {!loaded ? (
          <Loading>Building your workout…</Loading>
        ) : loaded.error ? (
          <ErrorNote>{loaded.error.message}</ErrorNote>
        ) : exercises.length === 0 ? (
          <Card className="text-center text-sm text-muted">No exercises fit these filters. Try another body part or turn off "No equipment".</Card>
        ) : (
          <div className="space-y-3">
            {loaded.data.note && (
              <Card tone="bg-brand-soft" className="text-sm text-brand-deep">
                {loaded.data.note}
              </Card>
            )}
            <ErrorNote>{logs.error && `Couldn't load today's logged exercises: ${logs.error.message}`}</ErrorNote>
            <Label className="px-1">
              {doneCount} of {exercises.length} done
            </Label>
            {exercises.map((e, i) => (
              <ExerciseCard
                key={`${i}-${e.id}`}
                exercise={e}
                done={Boolean(logFor(e.id))}
                open={expanded.has(e.id)}
                onToggle={() => toggleExpanded(e.id)}
                swapping={swapping === i}
                busy={logBusy === e.id}
                disabled={swapping !== null}
                notice={notice?.index === i ? notice : null}
                onSwap={() => swap(i)}
                onComplete={() => complete(i)}
                onUndo={() => undo(i)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

// A pill that toggles on and off; looks like ChipScroller's chips
function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`shrink-0 snap-start rounded-full px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
        active ? 'bg-ink text-white' : 'bg-surface text-ink ring-1 ring-line hover:ring-ink/30'
      }`}
    >
      {children}
    </button>
  )
}

function ExerciseCard({ exercise: e, done, open, onToggle, swapping, busy, disabled, notice, onSwap, onComplete, onUndo }) {
  const steps = e.how_to || []
  const muscles = e.muscles.map((m) => MUSCLE_LABEL[m] || m).join(', ')
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12px] font-semibold text-brand">{KIND_LABEL[e.kind] || e.kind}</p>
          <p className="mt-0.5 text-[17px] leading-snug font-semibold">{e.name}</p>
          <p className="mt-0.5 text-sm text-muted">
            {e.equipment}
            {muscles && ` · ${muscles}`}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-semibold">{dose(e)}</p>
          {e.kcal != null && <p className="text-[13px] text-muted">~{fmt(e.kcal)} kcal</p>}
        </div>
      </div>

      {(steps.length > 0 || e.tip || e.video_url) && (
        <button type="button" onClick={onToggle} aria-expanded={open} className="mt-3 flex items-center gap-1 text-sm font-semibold text-brand">
          {open ? 'Hide steps' : 'How to do it'}
          <svg viewBox="0 0 24 24" className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
      )}
      {open && (
        <div className="mt-3 space-y-3 rounded-xl bg-bg p-4 text-sm">
          {steps.length > 0 && (
            <ol className="list-decimal space-y-1.5 pl-5">
              {steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          )}
          {e.tip && (
            <p className="text-muted">
              <span className="font-semibold text-ink">Tip:</span> {e.tip}
            </p>
          )}
          {e.video_url && (
            <a href={e.video_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-brand">
              Watch video
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M7 17 17 7M9 7h8v8" />
              </svg>
            </a>
          )}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        {done ? (
          <>
            <p className="flex flex-1 items-center gap-1.5 rounded-xl bg-good/10 px-4 py-3 text-sm font-semibold text-good">✓ Completed</p>
            <Button variant="soft" onClick={onUndo} disabled={busy} className="!py-3">
              {busy ? 'Undoing…' : 'Undo'}
            </Button>
          </>
        ) : (
          <>
            {/* The cool-down stretch is always the same, so there is nothing to swap it for */}
            {e.kind !== 'mobility' && (
              <Button variant="soft" onClick={onSwap} disabled={disabled || busy} className="!py-3">
                {swapping ? 'Swapping…' : 'Swap'}
              </Button>
            )}
            <Button onClick={onComplete} disabled={busy || swapping} className="flex-1 !py-3">
              {busy ? 'Saving…' : 'I completed this'}
            </Button>
          </>
        )}
      </div>
      {notice && <p className={`mt-2 text-[13px] ${notice.error ? 'text-bad' : 'text-muted'}`}>{notice.text}</p>}
    </Card>
  )
}
