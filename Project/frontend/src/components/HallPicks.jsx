import { useEffect, useState } from 'react'
import { getHallPicks } from '../api'
import { Card, Label } from './ui'

const fmt = (n) => (n == null ? '—' : Math.round(n))
const shortHall = (hall) => hall.match(/\(([^)]+)\)\s*$/)?.[1] || hall
// Scores within this many points of the best count as the same: a point or two between big halls means nothing
const TIE = 2

// "Where should I eat?": every hall that serves this meal, ranked by how well the best plate there
// fits what the user still needs, plus the plate with the most protein inside the same calories.
// Tap a hall to open it. Shows nothing without a goal (the meal card asks for one) or if it can't load.
export default function HallPicks({ userId, date, group, hall, onPickHall, version }) {
  const [state, setState] = useState({ key: null })
  const key = `${userId}|${date}|${group}|${version}`

  useEffect(() => {
    let ignore = false
    getHallPicks(userId, date, group)
      .then((picks) => !ignore && setState({ key, picks }))
      .catch((error) => !ignore && setState({ key, error }))
    return () => {
      ignore = true
    }
  }, [key, userId, date, group])

  if (state.key !== key) return <Card className="text-sm text-muted">Comparing dining halls…</Card>
  if (state.error) return null
  if (!state.picks.halls.length) {
    // Nothing left to compare: say so when it is because the meal's budget is used up
    return state.picks.target.kcal < 50 ? <Card className="text-sm text-muted">You have used up your {group} budget today, so there is nothing left to compare.</Card> : null
  }

  const { halls, best_protein: bestProtein } = state.picks
  const top = halls[0].match
  const protein = halls.find((h) => h.hall === bestProtein)

  return (
    <Card>
      <Label className="mb-1">Best hall for your {group}</Label>
      <p className="text-[13px] text-muted">How well the best plate at each hall fits what you still need at this meal.</p>

      <ul className="mt-3 space-y-1.5">
        {halls.map((h) => {
          const selected = h.hall === hall
          const great = top - h.match <= TIE
          return (
            <li key={h.hall}>
              <button
                type="button"
                onClick={() => onPickHall(h.hall)}
                aria-pressed={selected}
                className={`w-full rounded-xl px-3 py-2.5 text-left transition-colors ${selected ? 'bg-brand-soft ring-1 ring-brand/40' : 'bg-bg active:bg-line/50'}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 font-semibold">
                    <span className="truncate">{shortHall(h.hall)}</span>
                    {great && <span className="shrink-0 rounded-full bg-good/10 px-2 py-0.5 text-[11px] font-semibold text-good">Great match</span>}
                  </span>
                  <span className="shrink-0 text-sm font-bold">{h.match}%</span>
                </span>
                <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
                  <span className={`block h-full rounded-full ${great ? 'bg-good' : 'bg-brand'}`} style={{ width: `${h.match}%` }} />
                </span>
                <span className="mt-1.5 block text-[12px] text-muted">
                  {fmt(h.tray.total.kcal)} kcal · {fmt(h.tray.total.protein_g)} g protein
                  {h.tray.note ? ` · ${h.tray.note.replace('Closest option: ', '')}` : ''}
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {protein && (
        <div className="mt-4 rounded-xl bg-ink p-3.5 text-white">
          <p className="text-[13px] font-semibold text-brand">Highest-protein plate today</p>
          <p className="mt-1 text-[15px] font-semibold">
            {shortHall(protein.hall)}: {fmt(protein.high_protein.total.protein_g)} g protein
            <span className="font-normal text-white/70"> in {fmt(protein.high_protein.total.kcal)} kcal ({protein.high_protein.protein_share}% of calories)</span>
          </p>
          <p className="mt-1 text-[13px] text-white/70">
            {protein.high_protein.items.map((l) => `${l.servings}× ${l.name}`).join(' · ')}
          </p>
          {protein.hall !== hall && (
            <button type="button" onClick={() => onPickHall(protein.hall)} className="mt-2.5 text-[13px] font-semibold text-brand">
              Open {shortHall(protein.hall)} →
            </button>
          )}
        </div>
      )}
    </Card>
  )
}
