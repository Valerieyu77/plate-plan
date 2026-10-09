import { useEffect, useState } from 'react'
import { addWeightLog, getProgress } from '../api'
import { Bar, ErrorNote, Field, Input, Loading, SectionHead } from '../components/ui'
import { todayISO } from '../constants'
import { getPrefs } from '../session'

const NUTRIENTS = [
  ['kcal', 'Calories', ''],
  ['protein_g', 'Protein', 'g'],
  ['carbs_g', 'Carbs', 'g'],
  ['fat_g', 'Fat', 'g'],
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
    <section className="pt-10 pb-24">
      <SectionHead n="03" title="Progress" sub="What you've checked off against your daily targets, and how your weight is moving." />

      <Field label="Date" className="mb-10 max-w-[220px]">
        <Input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
      </Field>

      {!current && <Loading />}
      {current?.error && <ErrorNote>{current.error.message}</ErrorNote>}
      {progress?.missingGoal && (
        <div className="border border-ink p-6">
          <p>Set a goal first to see your targets.</p>
          <button onClick={onSetGoal} className="mt-4 bg-ink px-5 py-3 text-sm font-medium text-paper transition-colors hover:bg-illini">
            Pick a goal
          </button>
        </div>
      )}

      {progress && !progress.missingGoal && (
        <div className="grid gap-16 lg:grid-cols-2">
          <div>
            <div className="flex items-end gap-4">
              <span className="font-serif text-8xl leading-none font-medium tracking-tight">{Math.round(progress.actual.kcal)}</span>
              <span className="pb-3 font-mono text-sm text-ink-soft">
                of {Math.round(progress.target.kcal)} kcal
                <br />
                <span className={progress.over.kcal > 0 ? 'text-illini-deep' : ''}>
                  {progress.over.kcal > 0 ? `${Math.round(progress.over.kcal)} over` : `${Math.round(progress.remaining.kcal)} left`}
                </span>
              </span>
            </div>
            <div className="mt-8 space-y-5">
              {NUTRIENTS.map(([key, label, unit]) => (
                <Bar key={key} label={label} value={progress.actual[key]} max={progress.target[key]} unit={unit} strong={key === 'kcal'} />
              ))}
            </div>
          </div>

          <div>
            <p className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">Weight (lb)</p>
            <WeightChart points={progress.weight_trend} target={targetWeight} />

            <form onSubmit={saveWeight} className="mt-6 flex flex-wrap items-end gap-2">
              <Field label="Weigh-in date" className="w-[170px]">
                <Input type="date" required max={todayISO()} value={weighIn.date} onChange={(e) => setWeighIn((w) => ({ ...w, date: e.target.value }))} />
              </Field>
              <Field label="Weight (lb)" className="w-[120px]">
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
              <button disabled={saving} className="bg-ink px-5 py-2.5 font-medium text-paper transition-colors hover:bg-illini disabled:opacity-60">
                {saving ? 'Saving…' : 'Log weight'}
              </button>
            </form>
            <div className="mt-3">
              <ErrorNote>{saveError}</ErrorNote>
            </div>

            {progress.weight_trend.length > 0 && (
              <ul className="mt-6 divide-y divide-rule border-y border-ink font-mono text-sm">
                {[...progress.weight_trend].reverse().slice(0, 7).map((w, i) => (
                  <li key={`${w.date}-${i}`} className="flex justify-between py-2">
                    <span className="text-ink-soft">{w.date}</span>
                    <span>{w.weight_lbs} lb</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

// Simple SVG line chart: one series (weight) plus a dashed line for the target weight
function WeightChart({ points, target }) {
  const [hover, setHover] = useState(null)
  if (points.length === 0) {
    return <p className="mt-3 border-y border-ink py-10 text-center text-ink-soft">No weigh-ins yet. Log one below to start your trend.</p>
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
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} stroke="var(--color-rule)" strokeWidth="1" />
            <text x={pad.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-ink-soft font-mono text-[11px]">
              {t}
            </text>
          </g>
        ))}
        <text x={pad.left} y={H - 6} className="fill-ink-soft font-mono text-[11px]">
          {points[0].date}
        </text>
        {points.length > 1 && (
          <text x={W - pad.right} y={H - 6} textAnchor="end" className="fill-ink-soft font-mono text-[11px]">
            {points.at(-1).date}
          </text>
        )}

        {target && (
          <g>
            <line x1={pad.left} x2={W - pad.right} y1={y(target)} y2={y(target)} stroke="var(--color-illini)" strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={W - pad.right} y={y(target) - 6} textAnchor="end" className="fill-ink font-mono text-[11px]">
              Target {target}
            </text>
          </g>
        )}

        {active && <line x1={active.cx} x2={active.cx} y1={pad.top} y2={H - pad.bottom} stroke="var(--color-ink-soft)" strokeWidth="1" />}
        {coords.length > 1 && (
          <polyline
            points={coords.map((c) => `${c.cx},${c.cy}`).join(' ')}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
        {coords.map((c, i) => (
          <circle key={i} cx={c.cx} cy={c.cy} r={hover === i ? 5 : 4} fill="var(--color-ink)" stroke="var(--color-paper)" strokeWidth="2" />
        ))}
      </svg>
      {active && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-full border border-ink bg-paper px-2 py-1 font-mono text-[12px] whitespace-nowrap"
          style={{ left: `${(active.cx / W) * 100}%`, top: `${(active.cy / H) * 100}%`, marginTop: -10 }}
        >
          {active.date} · {active.weight_lbs} lb
        </div>
      )}
    </div>
  )
}
