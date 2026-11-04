import { useEffect, useState } from 'react'
import { addWeightLog, getGoalProgress, getGoalTimeline, getProgress } from '../api'
import { Bar, Button, Card, DateChip, ErrorNote, Field, Input, Label, Loading, PageHeader, ProgressRing } from '../components/ui'
import { todayISO } from '../constants'
import { fmtDate } from '../format'

const MACROS = [
  ['protein_g', 'Protein', 'bg-ink'],
  ['carbs_g', 'Carbs', 'bg-brand'],
  ['fat_g', 'Fat', 'bg-muted'],
]

const STATUS = {
  on_track: ['On track', 'bg-good/10 text-good'],
  ahead: ['Ahead of plan', 'bg-good/10 text-good'],
  behind: ['Behind plan', 'bg-brand-soft text-brand-deep'],
  reached: ['Goal reached', 'bg-good/10 text-good'],
}

// Goal progress: [label, tone] for each status
const PACE = {
  ahead: ['Ahead of plan', 'bg-good/10 text-good'],
  on_track: ['On track', 'bg-good/10 text-good'],
  behind: ['Behind plan', 'bg-brand-soft text-brand-deep'],
  over: ['Over your goal', 'bg-brand-soft text-brand-deep'],
  under: ['Under your goal', 'bg-brand-soft text-brand-deep'],
  not_logged: ['No logs yet', 'bg-bg text-muted'],
  unsafe_pace: ['Unsafe pace', 'bg-bad/10 text-bad'],
}

async function loadProgress(userId, date) {
  try {
    const [progress, timeline, goalProgress] = await Promise.all([
      getProgress(userId, date),
      getGoalTimeline(userId).catch((err) => (err.status === 404 ? null : Promise.reject(err))),
      // 422 when the profile is missing what the burn estimate needs; the rest of the page still works
      getGoalProgress(userId, date).catch((err) => (err.status === 422 ? null : Promise.reject(err))),
    ])
    return { ...progress, timeline, goalProgress }
  } catch (err) {
    if (err.status === 404) return { missingGoal: true }
    throw err
  }
}

export default function ProgressPage({ user, onSetGoal }) {
  const [date, setDate] = useState(todayISO())
  const [data, setData] = useState({ key: null })
  const [weighIn, setWeighIn] = useState({ date: todayISO(), weight: '' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let ignore = false
    loadProgress(user.id, date)
      .then((progress) => !ignore && setData({ key: date, progress }))
      .catch((error) => !ignore && setData({ key: date, error }))
    return () => {
      ignore = true
    }
  }, [user.id, date])
  const current = data.key === date ? data : null
  const progress = current?.progress

  const saveWeight = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await addWeightLog(user.id, weighIn.date, Number(weighIn.weight))
      setWeighIn((w) => ({ ...w, weight: '' }))
      const fresh = await loadProgress(user.id, date)
      setData({ key: date, progress: fresh })
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section>
      <PageHeader title="Progress" sub="Today's food against your targets, and your weight trend." action={<DateChip value={date} onChange={setDate} />} />

      {!current && <Loading />}
      {current?.error && <ErrorNote>{current.error.message}</ErrorNote>}
      {progress?.missingGoal && (
        <Card>
          <p className="font-medium">Set a goal first to see your targets.</p>
          <Button onClick={onSetGoal} className="mt-4 w-full">
            Pick a goal
          </Button>
        </Card>
      )}

      {progress && !progress.missingGoal && (
        <div className="space-y-4">
          <Card className="flex flex-col items-center pt-6">
            <ProgressRing
              value={progress.actual.kcal}
              max={progress.target.kcal}
              size={200}
              stroke={16}
              label={`${Math.round(progress.actual.kcal)} of ${Math.round(progress.target.kcal)} kcal eaten`}
            >
              <p className="text-4xl leading-none font-bold tracking-tight">{Math.round(progress.actual.kcal)}</p>
              <p className="mt-1 text-[13px] text-muted">of {Math.round(progress.target.kcal)} kcal</p>
            </ProgressRing>
            <p className={`mt-4 rounded-full px-3 py-1 text-sm font-semibold ${progress.over.kcal > 0 ? 'bg-bad/10 text-bad' : 'bg-good/10 text-good'}`}>
              {progress.over.kcal > 0 ? `${Math.round(progress.over.kcal)} kcal over` : `${Math.round(progress.remaining.kcal)} kcal left`}
            </p>
            <div className="mt-6 w-full space-y-4">
              {MACROS.map(([key, label, color]) => (
                <Bar key={key} label={label} value={progress.actual[key]} max={progress.target[key]} unit="g" color={color} />
              ))}
            </div>
          </Card>

          {progress.goalProgress && <GoalProgressCard data={progress.goalProgress} latestWeighIn={progress.weight_trend.at(-1)} />}

          <Card>
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-bold">Weight</h2>
              {progress.weight_trend.length > 0 && (
                <p className="text-sm text-muted">
                  Latest <span className="font-semibold text-ink">{progress.weight_trend.at(-1).weight_lbs} lb</span>
                </p>
              )}
            </div>
            {progress.timeline && <TimelineSummary timeline={progress.timeline} />}
            <WeightChart points={progress.weight_trend} planned={progress.timeline?.planned} target={progress.timeline?.target_weight_lbs} />

            <form onSubmit={saveWeight} className="mt-4 grid grid-cols-2 gap-3">
              <Field label="Date">
                <Input type="date" required max={todayISO()} value={weighIn.date} onChange={(e) => setWeighIn((w) => ({ ...w, date: e.target.value }))} />
              </Field>
              <Field label="Weight (lb)">
                <Input
                  type="number"
                  required
                  inputMode="decimal"
                  min="50"
                  max="700"
                  step="0.1"
                  value={weighIn.weight}
                  onChange={(e) => setWeighIn((w) => ({ ...w, weight: e.target.value }))}
                />
              </Field>
              <Button disabled={saving} variant="dark" className="col-span-2">
                {saving ? 'Saving…' : 'Log weight'}
              </Button>
            </form>
            <div className="mt-3">
              <ErrorNote>{saveError}</ErrorNote>
            </div>

            {progress.weight_trend.length > 0 && (
              <div className="mt-4">
                <Label className="mb-1">Recent weigh-ins</Label>
                <ul className="divide-y divide-line text-sm">
                  {[...progress.weight_trend].reverse().slice(0, 7).map((w, i) => (
                    <li key={`${w.date}-${i}`} className="flex justify-between py-2.5">
                      <span className="text-muted">{w.date}</span>
                      <span className="font-semibold">{w.weight_lbs} lb</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </div>
      )}
    </section>
  )
}

// How the logged days add up toward the goal, and the weight the logs suggest next to the scale's
function GoalProgressCard({ data, latestWeighIn }) {
  const unsafe = data.status === 'unsafe_pace'
  const [label, tone] = PACE[data.status] || PACE.on_track
  // The timeline's latest weigh-in; goals without a timeline have no `scale`, so use the latest log
  const scaleWeight = data.scale?.latest_weight_lbs ?? latestWeighIn?.weight_lbs
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Goal progress</h2>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[12px] font-semibold ${tone}`}>{label}</span>
      </div>

      {unsafe ? (
        <p role="alert" className="mt-3 flex gap-2.5 rounded-xl bg-bad/10 p-3.5 text-sm text-bad">
          <svg viewBox="0 0 24 24" className="mt-px h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3 2 20h20L12 3ZM12 10v4M12 17h.01" />
          </svg>
          <span>{data.message}</span>
        </p>
      ) : (
        <>
          <p className="mt-2 text-[15px]">{data.message}</p>
          {data.projected_finish_date && (
            <p className="mt-1 text-sm text-muted">
              Projected finish <span className="font-semibold text-ink">{fmtDate(data.projected_finish_date)}</span>
              {data.target_date && <> · target {fmtDate(data.target_date)}</>}
            </p>
          )}
        </>
      )}

      {/* Above the weights: the message says "The estimates below use that" */}
      {data.calibration?.message && <p className="mt-4 border-t border-line pt-3 text-[13px] text-muted">{data.calibration.message}</p>}

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-bg p-3.5">
          <Label>Estimated weight</Label>
          <p className="mt-1 text-2xl font-bold tracking-tight">
            {data.weight.estimated_weight_lbs} <span className="text-sm font-semibold text-muted">lb</span>
          </p>
          <p className="mt-0.5 text-[12px] text-muted">From your logs since {fmtDate(data.weight.from_date)}</p>
        </div>
        <div className="rounded-xl bg-bg p-3.5">
          <Label>Scale weight</Label>
          <p className="mt-1 text-2xl font-bold tracking-tight">
            {scaleWeight ?? '—'} {scaleWeight != null && <span className="text-sm font-semibold text-muted">lb</span>}
          </p>
          <p className="mt-0.5 text-[12px] text-muted">{latestWeighIn ? `Weighed in ${fmtDate(latestWeighIn.date)}` : 'No weigh-in yet'}</p>
        </div>
      </div>
    </Card>
  )
}

function TimelineSummary({ timeline: t }) {
  const [label, tone] = STATUS[t.status]
  return (
    <div className="mt-3 rounded-xl bg-bg p-3.5 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${tone}`}>{label}</span>
        <span className="text-muted">
          {t.target_weight_lbs} lb by {fmtDate(t.target_date)}
        </span>
      </div>
      {t.status !== 'reached' && (
        <p className="mt-2 text-muted">
          By your last weigh-in the plan expected <span className="font-semibold text-ink">{t.expected_weight_lbs} lb</span>.{' '}
          {Math.abs(t.remaining_lbs)} lb to go.
          {t.projected_finish_date && t.projected_finish_date > t.target_date && (
            <> At a safe pace you'll get there around {fmtDate(t.projected_finish_date)}.</>
          )}
        </p>
      )}
    </div>
  )
}

// Simple SVG line chart: logged weight, the planned path (dashed, when the goal has a timeline)
// and a dashed line for the target weight
function WeightChart({ points, planned = [], target }) {
  const [hover, setHover] = useState(null)
  if (points.length === 0 && planned.length === 0) {
    return <p className="mt-3 rounded-xl bg-bg py-8 text-center text-sm text-muted">No weigh-ins yet. Log one below to start your trend.</p>
  }

  const W = 520
  const H = 220
  const pad = { top: 16, right: 16, bottom: 28, left: 40 }
  const values = points.concat(planned).map((p) => p.weight_lbs).concat(target ? [target] : [])
  const lo = Math.floor(Math.min(...values) - 2)
  const hi = Math.ceil(Math.max(...values) + 2)
  const times = points.map((p) => new Date(p.date).getTime())
  const allTimes = times.concat(planned.map((p) => new Date(p.date).getTime()))
  const t0 = Math.min(...allTimes)
  const t1 = Math.max(...allTimes)
  const first = points.concat(planned).reduce((a, b) => (a.date <= b.date ? a : b))
  const last = points.concat(planned).reduce((a, b) => (a.date >= b.date ? a : b))
  const x = (t) => (t1 === t0 ? (pad.left + W - pad.right) / 2 : pad.left + ((t - t0) / (t1 - t0)) * (W - pad.left - pad.right))
  const y = (v) => pad.top + ((hi - v) / (hi - lo)) * (H - pad.top - pad.bottom)
  const coords = points.map((p, i) => ({ ...p, cx: x(times[i]), cy: y(p.weight_lbs) }))
  const ticks = [lo, Math.round((lo + hi) / 2), hi]
  const active = hover !== null ? coords[hover] : null

  const onMove = (e) => {
    if (coords.length === 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = ((e.clientX - rect.left) / rect.width) * W
    let best = 0
    coords.forEach((c, i) => {
      if (Math.abs(c.cx - mx) < Math.abs(coords[best].cx - mx)) best = i
    })
    setHover(best)
  }

  return (
    <div className="relative mt-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={points.length ? `Weight trend, ${points.length} weigh-ins, latest ${points.at(-1).weight_lbs} lb` : 'Planned weight'}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeWidth="1" />
            <text x={pad.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px]">
              {t}
            </text>
          </g>
        ))}
        <text x={pad.left} y={H - 6} className="fill-muted text-[11px]">
          {first.date}
        </text>
        {last.date !== first.date && (
          <text x={W - pad.right} y={H - 6} textAnchor="end" className="fill-muted text-[11px]">
            {last.date}
          </text>
        )}

        {planned.length > 1 && (
          <polyline
            points={planned.map((p) => `${x(new Date(p.date).getTime())},${y(p.weight_lbs)}`).join(' ')}
            fill="none"
            stroke="var(--color-muted)"
            strokeWidth="1.5"
            strokeDasharray="3 4"
          />
        )}

        {target && (
          <g>
            <line x1={pad.left} x2={W - pad.right} y1={y(target)} y2={y(target)} stroke="var(--color-brand)" strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={W - pad.right} y={y(target) - 6} textAnchor="end" className="fill-brand-deep text-[11px] font-semibold">
              Target {target}
            </text>
          </g>
        )}

        {active && <line x1={active.cx} x2={active.cx} y1={pad.top} y2={H - pad.bottom} stroke="var(--color-muted)" strokeWidth="1" />}
        {coords.length > 1 && (
          <polyline
            points={coords.map((c) => `${c.cx},${c.cy}`).join(' ')}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
        {coords.map((c, i) => (
          <circle key={i} cx={c.cx} cy={c.cy} r={hover === i ? 5 : 4} fill="var(--color-ink)" stroke="var(--color-surface)" strokeWidth="2" />
        ))}
      </svg>
      {active && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-full rounded-lg bg-ink px-2.5 py-1 text-[12px] font-medium whitespace-nowrap text-white shadow-lg"
          style={{ left: `${(active.cx / W) * 100}%`, top: `${(active.cy / H) * 100}%`, marginTop: -10 }}
        >
          {active.date} · {active.weight_lbs} lb
        </div>
      )}
    </div>
  )
}
