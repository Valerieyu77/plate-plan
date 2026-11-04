import { useEffect, useState } from 'react'
import { getGoal, getHallPicks, getProgress } from '../api'
import { GREAT_MIN, TIE } from '../components/HallPicks'
import { Bar, ButtonLink, Card, Label, ProgressRing } from '../components/ui'
import { GOALS, defaultGroup, todayISO } from '../constants'
import { fmt, shortHall } from '../format'

// Each card shows a small picture of its page. Signed in, it's drawn from the user's own goal, today's food and
// today's hall picks; anything missing (signed out, no goal yet, a failed request) shows the example below instead,
// marked "Example". The examples use the API's own shapes, so both go through the same drawing code.
const EXAMPLE_GOAL = { calorie_goal: 1850, protein_goal_g: 140, carb_goal_g: 185, fat_goal_g: 62 }

const EXAMPLE_PICKS = {
  halls: [
    {
      hall: 'Illinois Street Dining Center (ISR)',
      match: 92,
      tray: {
        items: [
          { name: 'Grilled Chicken Breast', servings: 1.5 },
          { name: 'Brown Rice', servings: 1 },
          { name: 'Steamed Broccoli', servings: 1 },
        ],
        total: { kcal: 620, protein_g: 48 },
      },
    },
    { hall: 'Ikenberry Dining Center (Ike)', match: 81 },
    { hall: 'Pennsylvania Avenue Dining Hall (PAR)', match: 74 },
  ],
}

const EXAMPLE_PROGRESS = {
  target: { kcal: 1850, protein_g: 140, carbs_g: 185, fat_g: 62 },
  actual: { kcal: 1240, protein_g: 96, carbs_g: 150, fat_g: 41 },
  weight_trend: [172, 171.4, 171.6, 170.8, 170.1, 169.5, 169.8, 168.9].map((weight_lbs) => ({ weight_lbs })),
}

const MINI_CARD = 'rounded-lg bg-surface shadow-[0_1px_2px_rgba(19,41,75,0.06)]'

// 1850 -> "1,850"; missing -> "—"
const big = (n) => fmt(n).toLocaleString()

function GoalPreview({ goal, goalType }) {
  const targets = [
    ['Calories', goal.calorie_goal, 'kcal'],
    ['Protein', goal.protein_goal_g, 'g'],
    ['Carbs', goal.carb_goal_g, 'g'],
    ['Fat', goal.fat_goal_g, 'g'],
  ]
  return (
    <>
      <div className="grid grid-cols-3 gap-1.5">
        {Object.entries(GOALS).map(([key, { label }]) => (
          <span key={key} className={`${MINI_CARD} px-2 py-2 text-center text-[12px] font-semibold ${key === goalType ? 'ring-2 ring-brand' : 'text-muted'}`}>
            {label}
          </span>
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        {targets.map(([label, value, unit], i) => (
          <div key={label} className={`${MINI_CARD} p-2.5 ${i === 0 ? '!bg-brand text-white' : ''}`}>
            <p className={`text-[11px] font-semibold ${i === 0 ? 'text-white/80' : 'text-muted'}`}>{label}</p>
            <p className="mt-1 text-lg leading-none font-bold tracking-tight">
              {big(value)}
              <span className={`ml-0.5 text-[11px] font-medium ${i === 0 ? 'text-white/80' : 'text-muted'}`}>{unit}</span>
            </p>
          </div>
        ))}
      </div>
    </>
  )
}

// The top three halls for the meal, and the plate at the best one
function PlanPreview({ picks, group }) {
  const top = picks.halls[0]
  const items = top.tray?.items || []
  return (
    <div className="grid gap-1.5 sm:grid-cols-2">
      <div className={`${MINI_CARD} space-y-1.5 p-2`}>
        <p className="px-0.5 text-[11px] font-semibold text-muted">Best hall for {group}</p>
        {picks.halls.slice(0, 3).map((h, i) => {
          const great = h.match >= GREAT_MIN && top.match - h.match <= TIE
          return (
            <div key={h.hall} className={`rounded-md px-2 py-1.5 ${i === 0 ? 'bg-brand-soft ring-1 ring-brand/40' : 'bg-bg'}`}>
              <div className="flex items-center justify-between gap-2 text-[13px] font-semibold">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className="truncate">{shortHall(h.hall)}</span>
                  {great && <span className="shrink-0 rounded-full bg-good/10 px-1.5 text-[10px] text-good">Great match</span>}
                </span>
                {h.match}%
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line">
                <div className={`h-full rounded-full ${great ? 'bg-good' : 'bg-brand'}`} style={{ width: `${h.match}%` }} />
              </div>
            </div>
          )
        })}
      </div>
      <div className="rounded-lg bg-ink p-2.5 text-white">
        <p className="text-[11px] font-semibold text-brand">Best plate at {shortHall(top.hall)}</p>
        <ol className="mt-1.5 space-y-1">
          {items.slice(0, 3).map((line, i) => (
            <li key={`${line.name}-${i}`} className="flex items-center gap-2 rounded-md bg-white/5 px-2 py-1.5 text-[12px]">
              <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-brand text-[10px] font-bold">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate font-medium">{line.name}</span>
              <span className="text-white/60">{line.servings}×</span>
            </li>
          ))}
        </ol>
        {items.length > 3 && <p className="mt-1 px-0.5 text-[11px] text-white/60">+ {items.length - 3} more</p>}
        {top.tray && (
          <p className="mt-1.5 text-[11px] text-white/70">
            Total <span className="font-semibold text-white">{big(top.tray.total.kcal)} kcal</span> · {fmt(top.tray.total.protein_g)} g protein
          </p>
        )}
      </div>
    </div>
  )
}

function ProgressPreview({ progress, targetWeight }) {
  const { actual, target, weight_trend: trend } = progress
  // The weigh-ins as a line in a 100 x 40 box, with the target weight dashed
  const weights = trend.map((p) => p.weight_lbs)
  const values = targetWeight ? [...weights, targetWeight] : weights
  const lo = Math.min(...values) - 1
  const hi = Math.max(...values) + 1
  const y = (w) => 4 + ((hi - w) / (hi - lo)) * 32
  const line = weights.map((w, i) => `${(i / (weights.length - 1)) * 100},${y(w)}`).join(' ')
  return (
    <div className="grid gap-1.5 sm:grid-cols-[3fr_2fr]">
      <div className={`${MINI_CARD} flex items-center gap-3 p-3`}>
        <ProgressRing value={actual.kcal} max={target.kcal} size={84} stroke={9} label="">
          <p className="text-base leading-none font-bold">{big(actual.kcal)}</p>
          <p className="mt-0.5 text-[10px] text-muted">of {big(target.kcal)}</p>
        </ProgressRing>
        <div className="min-w-0 flex-1 space-y-2">
          <Bar label="Protein" value={actual.protein_g} max={target.protein_g} unit="g" />
          <Bar label="Carbs" value={actual.carbs_g} max={target.carbs_g} unit="g" color="bg-brand" />
          <Bar label="Fat" value={actual.fat_g} max={target.fat_g} unit="g" color="bg-muted" />
        </div>
      </div>
      <div className={`${MINI_CARD} flex flex-col p-3`}>
        <div className="flex items-baseline justify-between text-[13px]">
          <span className="font-semibold">Weight</span>
          {weights.length > 0 && (
            <span className="text-muted">
              <span className="font-semibold text-ink">{weights.at(-1)}</span> lb
            </span>
          )}
        </div>
        {weights.length >= 2 ? (
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="mt-2 h-14 w-full flex-1">
            {targetWeight && (
              <line x1="0" x2="100" y1={y(targetWeight)} y2={y(targetWeight)} stroke="var(--color-muted)" strokeWidth="1.5" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
            )}
            <polyline points={line} fill="none" stroke="var(--color-brand)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
          </svg>
        ) : (
          <p className="mt-2 flex-1 text-[12px] text-muted">Log two weigh-ins to see your trend.</p>
        )}
        {targetWeight && <p className="mt-1 text-[11px] text-muted">Target {targetWeight} lb</p>}
      </div>
    </div>
  )
}

// The three parts of the app, in the order a new user goes through them (sign up / log in is in the header).
// `mine` picks the preview's props out of the user's loaded data, or returns nothing to show the example.
const SECTIONS = [
  {
    href: '#/goal',
    title: 'Goal',
    tagline: 'Pick a goal and get your daily targets.',
    link: 'Set your goal',
    Preview: GoalPreview,
    example: { goal: EXAMPLE_GOAL, goalType: 'lose' },
    mine: (data) => data.goal && { goal: data.goal, goalType: data.goal.goal_type },
  },
  {
    href: '#/plan',
    title: 'Plan',
    tagline: 'Find the hall and dishes that fit your next meal.',
    link: 'Plan a meal',
    Preview: PlanPreview,
    example: { picks: EXAMPLE_PICKS, group: 'lunch' },
    mine: (data) => data.picks?.halls?.length > 0 && { picks: data.picks, group: data.group },
  },
  {
    href: '#/progress',
    title: 'Progress',
    tagline: 'Track what you eat and how your weight changes.',
    link: 'See your progress',
    Preview: ProgressPreview,
    example: { progress: EXAMPLE_PROGRESS, targetWeight: 165 },
    mine: (data) => data.progress && { progress: data.progress, targetWeight: data.goal?.target_weight_lbs },
  },
]

export default function HomePage({ user }) {
  const userId = user?.id ?? null
  const [data, setData] = useState({ userId: null })

  // Loaded every time home opens, so it reflects the latest goal and logs
  useEffect(() => {
    if (userId === null) return
    let ignore = false
    const today = todayISO()
    const group = defaultGroup()
    // No goal yet (404) or a failed request just leaves that card on its example
    const orNull = (request) => request.catch(() => null)
    Promise.all([orNull(getGoal(userId)), orNull(getProgress(userId, today)), orNull(getHallPicks(userId, today, group))]).then(
      ([goal, progress, picks]) => !ignore && setData({ userId, goal, progress, picks, group }),
    )
    return () => {
      ignore = true
    }
  }, [userId])

  const loading = userId !== null && data.userId !== userId
  const loaded = userId !== null && !loading ? data : null

  return (
    <section>
      <div className="pt-4 pb-6">
        <p className="text-[13px] font-semibold text-brand">
          {user ? `Welcome back, ${user.name.trim().split(/\s+/)[0]}` : 'For UIUC students and staff'}
        </p>
        <h1 className="mt-2 text-[2rem] leading-tight font-bold tracking-tight">Know what to eat before you reach the dining hall.</h1>
        <p className="mt-3 text-muted">
          Plate Plan reads today's Illinois dining menus, sets calorie and macro targets for your goal, and shows which dishes fit your next meal.
        </p>
        {user && (
          <ButtonLink href="#/plan" className="mt-5 w-full">
            Plan my next meal
          </ButtonLink>
        )}
      </div>

      <Label>What you can do</Label>
      {!user && <p className="mt-1 text-sm text-muted">Sign up at the top right to try them with your own numbers.</p>}
      <ol className="mt-3 space-y-3">
        {SECTIONS.map(({ href, title, tagline, link, Preview, example, mine }, i) => {
          const own = loaded && mine(loaded)
          return (
            <li key={href}>
              <Card className="relative ring-2 ring-transparent transition hover:ring-line">
                <div className="flex items-center gap-3">
                  <span aria-hidden="true" className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-soft text-[13px] font-bold text-brand-deep">
                    {i + 1}
                  </span>
                  <h2 className="text-lg font-bold">{title}</h2>
                  {!loading && !own && <span className="ml-auto rounded-full bg-bg px-2 py-0.5 text-[11px] font-semibold text-muted">Example</span>}
                </div>
                <p className="mt-1 text-[15px] text-muted">{tagline}</p>
                <div aria-hidden="true" className="mt-3 rounded-xl bg-bg p-2">
                  {loading ? <p className="py-10 text-center text-[13px] text-muted">Loading your numbers…</p> : <Preview {...(own || example)} />}
                </div>
                {/* The link stretches over the whole card (after:inset-0), so a tap anywhere on it opens the section */}
                <a href={href} className="mt-4 inline-flex items-center gap-1 text-[15px] font-semibold text-brand after:absolute after:inset-0 after:rounded-2xl">
                  {link}
                  <span aria-hidden="true">→</span>
                </a>
              </Card>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
