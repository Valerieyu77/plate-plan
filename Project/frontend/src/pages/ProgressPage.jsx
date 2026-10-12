import { useEffect, useState } from 'react'
import { addWeightLog, getProgress } from '../api'
import { Bar, Button, Card, DateChip, ErrorNote, Field, Input, Label, Loading, PageHeader, ProgressRing } from '../components/ui'
import { todayISO } from '../constants'
import { getPrefs } from '../session'

const MACROS = [
  ['protein_g', 'Protein', 'bg-ink'],
  ['carbs_g', 'Carbs', 'bg-brand'],
  ['fat_g', 'Fat', 'bg-muted'],
]

async function loadProgress(userId, date) {
  try {
    return await getProgress(userId, date)
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
  const targetWeight = getPrefs(user.id).targetWeight

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

          <Card>
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-bold">Weight</h2>
              {progress.weight_trend.length > 0 && (
                <p className="text-sm text-muted">
                  Latest <span className="font-semibold text-ink">{progress.weight_trend.at(-1).weight_lbs} lb</span>
                </p>
              )}
            </div>
            <WeightChart points={progress.weight_trend} target={targetWeight} />

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

// Simple SVG line chart: one series (weight) plus a dashed line for the target weight
function WeightChart({ points, target }) {
  const [hover, setHover] = useState(null)
  if (points.length === 0) {
    return <p className="mt-3 rounded-xl bg-bg py-8 text-center text-sm text-muted">No weigh-ins yet. Log one below to start your trend.</p>
  }

  const W = 520
  const H = 220
  const pad = { top: 16, right: 16, bottom: 28, left: 40 }
  const values = points.map((p) => p.weight_lbs).concat(target ? [target] : [])
  const lo = Math.floor(Math.min(...values) - 2)
  const hi = Math.ceil(Math.max(...values) + 2)
  const times = points.map((p) => new Date(p.date).getTime())
  const t0 = Math.min(...times)
  const t1 = Math.max(...times)
  const x = (t) => (t1 === t0 ? (pad.left + W - pad.right) / 2 : pad.left + ((t - t0) / (t1 - t0)) * (W - pad.left - pad.right))
  const y = (v) => pad.top + ((hi - v) / (hi - lo)) * (H - pad.top - pad.bottom)
  const coords = points.map((p, i) => ({ ...p, cx: x(times[i]), cy: y(p.weight_lbs) }))
  const ticks = [lo, Math.round((lo + hi) / 2), hi]
  const active = hover !== null ? coords[hover] : null

  const onMove = (e) => {
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
        aria-label={`Weight trend, ${points.length} weigh-ins, latest ${points.at(-1).weight_lbs} lb`}
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
          {points[0].date}
        </text>
        {points.length > 1 && (
          <text x={W - pad.right} y={H - 6} textAnchor="end" className="fill-muted text-[11px]">
            {points.at(-1).date}
          </text>
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
