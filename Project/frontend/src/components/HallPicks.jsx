import { useEffect, useRef, useState } from 'react'
import { getHallPicks } from '../api'
import { fmt, shortHall } from '../format'
import { Button, Card, Label } from './ui'

// Scores within this many points of the best count as the same: a point or two between big halls means nothing
export const TIE = 2
// ...and a hall is only a "great match" if its plate really fits, however the others did
export const GREAT_MIN = 75
// After the first look, wait this long once something is logged, so a run of stepper taps asks only once
const REFRESH_DELAY_MS = 500

// "Where should I eat?": every hall that serves this meal, ranked by how well the best plate there
// fits what the user still needs, plus the plate with the most protein inside the same calories.
// Tap a hall to open it. `version` goes up whenever something is logged, which re-runs the comparison.
export default function HallPicks({ userId, date, group, hall, favorites, onPickHall, version }) {
  const scope = `${userId}|${date}|${group}`
  const [state, setState] = useState({ scope: null })
  const [attempt, setAttempt] = useState(0)
  const loadedScope = useRef(null)

  useEffect(() => {
    let ignore = false
    // A new day or meal loads at once; a change to what is logged waits a moment and keeps the old picks on screen
    const timer = setTimeout(
      () => {
        getHallPicks(userId, date, group)
          .then((picks) => {
            if (ignore) return
            loadedScope.current = scope
            setState({ scope, picks })
          })
          .catch((error) => !ignore && setState((s) => (s.scope === scope && s.picks ? s : { scope, error })))
      },
      loadedScope.current === scope ? REFRESH_DELAY_MS : 0,
    )
    return () => {
      ignore = true
      clearTimeout(timer)
    }
  }, [scope, userId, date, group, version, attempt])

  const retry = () => {
    loadedScope.current = null
    setState({ scope: null })
    setAttempt((a) => a + 1)
  }

  if (state.scope !== scope) return <Card className="text-sm text-muted">Comparing dining halls…</Card>

  if (state.error) {
    const { status, message } = state.error
    // No goal yet (the meal card asks for one) or the server doesn't have this feature yet: show nothing
    if (status === 404 && (/goal/i.test(message) || message === 'Not Found')) return null
    return (
      <Card className="flex items-center justify-between gap-3 text-sm text-muted">
        <span>Couldn't compare halls. {message}</span>
        <Button variant="soft" onClick={retry} className="shrink-0 !px-4 !py-2">
          Try again
        </Button>
      </Card>
    )
  }

  const { halls, best_protein: bestProtein, target } = state.picks
  if (!halls.length) {
    return (
      <Card className="text-sm text-muted">
        {target.kcal < 50 ? `You have used up your ${group} budget today, so there is nothing left to compare.` : `No hall has a plate that fits your allergies and diet for ${group}.`}
      </Card>
    )
  }

  const top = halls[0].match
  const protein = halls.find((h) => h.hall === bestProtein && h.high_protein.items.length > 0)

  return (
    <Card>
      <Label className="mb-1">Best hall for your {group}</Label>
      <p className="text-[13px] text-muted">How well the best plate at each hall fits what you still need at this meal.</p>

      <ul className="mt-3 space-y-1.5">
        {halls.map((h) => {
          const selected = h.hall === hall
          const great = h.match >= GREAT_MIN && top - h.match <= TIE
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
                    <span className="truncate">
                      {favorites?.has(h.hall) && <span className="text-brand" aria-label="Favorite">★ </span>}
                      {shortHall(h.hall)}
                    </span>
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
          <p className="text-[13px] font-semibold text-brand">Highest-protein {group} plate</p>
          <p className="mt-1 text-[15px] font-semibold">
            {shortHall(protein.hall)}: {fmt(protein.high_protein.total.protein_g)} g protein
            <span className="font-normal text-white/70"> in {fmt(protein.high_protein.total.kcal)} kcal ({protein.high_protein.protein_share}% of calories)</span>
          </p>
          <p className="mt-1 text-[13px] text-white/70">{protein.high_protein.items.map((l) => `${l.servings}× ${l.name}`).join(' · ')}</p>
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
