import { useEffect, useState } from 'react'
import { getEnergy, getEvents, getGoal, getHallPicks, getProgress } from '../api'
import { GREAT_MIN, TIE } from '../components/HallPicks'
import QuickAddButton from '../components/QuickAdd'
import { Bar, ButtonLink, Card, Label, Loading, ProgressRing } from '../components/ui'
import { GOALS, defaultGroup, todayISO } from '../constants'
import { fmt, isoInDays, shortHall } from '../format'

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
// Once the user has a goal, Home shows only their own previews, under `own.title` and `own.link`, in `own.order`
// (the tab bar's order: the next meal first).
const SECTIONS = [
  {
    href: '#/goal',
    title: 'Goal',
    tagline: 'Pick a goal and get your daily targets.',
    link: 'Set your goal',
    own: { title: 'Your targets', link: 'Change your goal', order: 3 },
    Preview: GoalPreview,
    example: { goal: EXAMPLE_GOAL, goalType: 'lose' },
    mine: (data) => data.goal && { goal: data.goal, goalType: data.goal.goal_type },
  },
  {
    href: '#/plan',
    title: 'Plan',
    tagline: 'Find the hall and dishes that fit your next meal.',
    link: 'Plan a meal',
    own: { title: 'Your next meal', link: 'Plan this meal', order: 1 },
    Preview: PlanPreview,
    example: { picks: EXAMPLE_PICKS, group: 'lunch' },
    mine: (data) => data.picks?.halls?.length > 0 && { picks: data.picks, group: data.group },
  },
  {
    href: '#/progress',
    title: 'Progress',
    tagline: 'Track what you eat and how your weight changes.',
    link: 'See your progress',
    own: { title: 'Your progress', link: 'See your progress', order: 2 },
    Preview: ProgressPreview,
    example: { progress: EXAMPLE_PROGRESS, targetWeight: 165 },
    mine: (data) => data.progress && { progress: data.progress, targetWeight: data.goal?.target_weight_lbs },
  },
]
const OWN_SECTIONS = [...SECTIONS].sort((a, b) => a.own.order - b.own.order)

// "Monday, November 9"
const todayLong = () => new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

export default function HomePage({ user }) {
  const userId = user?.id ?? null
  // The meals the user eats, as a string so the effect below doesn't re-run for an equal new array
  const mealsKey = user?.meals?.join(',') || ''
  const [data, setData] = useState({ userId: null })

  // Loaded every time home opens, so it reflects the latest goal and logs
  useEffect(() => {
    if (userId === null) return
    let ignore = false
    const today = todayISO()
    const group = defaultGroup(mealsKey ? mealsKey.split(',') : null)
    // No goal yet (404) or a failed request just leaves that card on its example
    const orNull = (request) => request.catch(() => null)
    Promise.all([orNull(getGoal(userId)), orNull(getProgress(userId, today)), orNull(getHallPicks(userId, today, group))]).then(
      ([goal, progress, picks]) => !ignore && setData({ userId, goal, progress, picks, group }),
    )
    return () => {
      ignore = true
    }
  }, [userId, mealsKey])

  const loading = userId !== null && data.userId !== userId
  const loaded = userId !== null && !loading ? data : null
  // Signed in with a goal, Home is the user's day rather than a tour of the app (while loading, assume a returning
  // user: new accounts go straight to the Goal page)
  const returning = userId !== null && (loading || Boolean(loaded?.goal))
  const firstName = user?.name.trim().split(/\s+/)[0]

  return (
    <section>
      <div className="pt-4 pb-6">
        {returning ? (
          <>
            <p className="text-[13px] font-semibold text-brand">{todayLong()}</p>
            <h1 className="mt-2 text-[2rem] leading-tight font-bold tracking-tight">Welcome back, {firstName}</h1>
          </>
        ) : (
          <>
            <p className="text-[13px] font-semibold text-brand">{user ? `Welcome back, ${firstName}` : 'For UIUC students and staff'}</p>
            <h1 className="mt-2 text-[2rem] leading-tight font-bold tracking-tight">Know what to eat before you reach the dining hall.</h1>
            <p className="mt-3 text-muted">
              Plate Plan reads today's Illinois dining menus, sets calorie and macro targets for your goal, and shows which dishes fit your next meal.
            </p>
          </>
        )}
        {user && (
          <ButtonLink href="#/plan" className="mt-5 w-full">
            Plan my next meal
          </ButtonLink>
        )}
      </div>

      {userId !== null && <TodayCalories userId={userId} />}

      {returning ? (
        // The user's own previews only; one without data (say, no menus today) is left out rather than shown as an example
        <div className="space-y-3">
          {OWN_SECTIONS.map(({ href, own: { title, link }, Preview, mine }) => {
            const props = loaded && mine(loaded)
            if (!loading && !props) return null
            return (
              <Card key={href} className="relative ring-2 ring-transparent transition hover:ring-line">
                <h2 className="text-lg font-bold">{title}</h2>
                <div aria-hidden="true" className="mt-3 rounded-xl bg-bg p-2">
                  {loading ? <p className="py-10 text-center text-[13px] text-muted">Loading your numbers…</p> : <Preview {...props} />}
                </div>
                <a href={href} className="mt-4 inline-flex items-center gap-1 text-[15px] font-semibold text-brand after:absolute after:inset-0 after:rounded-2xl">
                  {link}
                  <span aria-hidden="true">→</span>
                </a>
              </Card>
            )
          })}
        </div>
      ) : (
        <OnboardingSteps user={user} loaded={loaded} />
      )}

      <EventsList />
    </section>
  )
}

// New visitors (and accounts without a goal yet): the three parts of the app as numbered steps, each with a preview
// drawn from the user's own data where there is some, or an example marked "Example"
function OnboardingSteps({ user, loaded }) {
  return (
    <>
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
                  {!own && <span className="ml-auto rounded-full bg-bg px-2 py-0.5 text-[11px] font-semibold text-muted">Example</span>}
                </div>
                <p className="mt-1 text-[15px] text-muted">{tagline}</p>
                <div aria-hidden="true" className="mt-3 rounded-xl bg-bg p-2">
                  <Preview {...(own || example)} />
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
    </>
  )
}

// The badge for today: [label, tone]. Today isn't over, so it says how much of the goal is left rather than
// "ahead" or "behind": half a day's food against a whole day's goal always looks ahead when losing (and behind
// when gaining). It doesn't use /energy's `status`, so it reads the same whether that says "ahead" or "in_progress".
function todayBadge({ eaten, calorie_goal: goal }) {
  if (eaten == null) return ['Nothing logged yet', 'bg-bg text-muted']
  const left = Math.round(goal - eaten)
  if (left >= 0) return [`${left.toLocaleString()} kcal left`, 'bg-good/10 text-good']
  return [`${(-left).toLocaleString()} kcal over`, 'bg-brand-soft text-brand-deep']
}

// -450 -> "−450", 120 -> "+120"
const signed = (n) => (n == null ? '—' : `${n < 0 ? '−' : n > 0 ? '+' : ''}${Math.abs(n).toLocaleString()}`)

// Within this many kcal of zero, the day's net reads "about even" (a maintain goal lands here)
const EVEN_KCAL = 50

// Where today's net ends up. `burned` is the whole day's burn, so eaten − burned read "−1,940 deficit" after
// breakfast. Instead assume the user eats up to their goal: what is logged can only grow, so a day under the goal
// ends at goal − burn (the plan), and a day already over it ends at least at eaten − burn. This never rewards
// eating less than the goal with a bigger number. Returns {net, note}.
function dayNet({ eaten, calorie_goal: goal, burned }) {
  const over = (eaten ?? 0) > goal
  const net = Math.round(Math.max(eaten ?? 0, goal) - burned)
  const kind = Math.abs(net) < EVEN_KCAL ? 'About even' : net < 0 ? 'Deficit' : 'Surplus'
  return { net, note: over ? `${kind} so far` : `${kind} at your goal` }
}

// Today's calories in and out. The backend only says "too_low" once a day is over, so the reminder to eat
// enough checks yesterday.
function TodayCalories({ userId }) {
  const [state, setState] = useState({ userId: null })
  const [version, setVersion] = useState(0) // goes up after a quick add, to reload the numbers
  const [added, setAdded] = useState(null) // the food just added, for a short confirmation

  useEffect(() => {
    let ignore = false
    Promise.all([getEnergy(userId, todayISO()), getEnergy(userId, isoInDays(-1)).catch(() => null)])
      .then(([today, yesterday]) => !ignore && setState({ userId, today, yesterday }))
      // No goal yet (404) or a profile missing what the burn needs (422): the sections below cover that
      .catch((error) => !ignore && setState({ userId, error }))
    return () => {
      ignore = true
    }
  }, [userId, version])

  if (state.userId !== userId) return null
  if (state.error) {
    return [404, 422].includes(state.error.status) ? null : <p className="mb-6 text-sm text-muted">Couldn't load today's calories. {state.error.message}</p>
  }

  const { today, yesterday } = state
  const [label, tone] = todayBadge(today)
  const net = dayNet(today)
  return (
    <Card className="mb-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Today's calories</h2>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[12px] font-semibold ${tone}`}>{label}</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <Stat label="Eaten" value={big(today.eaten)} note={`of ${big(today.calorie_goal)} goal`} />
        {/* `burned` is an estimate for the whole day, not what has been burned by now */}
        <Stat label="Burn today" value={big(today.burned)} note={today.exercise > 0 ? `Incl. ${big(today.exercise)} from workouts` : 'Estimate, whole day'} />
        <Stat label="Day's net" value={signed(net.net)} note={net.note} />
      </div>

      {yesterday?.status === 'too_low' && (
        <p role="alert" className="mt-4 flex gap-2.5 rounded-xl bg-bad/10 p-3.5 text-sm text-bad">
          <svg viewBox="0 0 24 24" className="mt-px h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3 2 20h20L12 3ZM12 10v4M12 17h.01" />
          </svg>
          <span>
            <span className="font-semibold">You didn't eat enough yesterday.</span> You logged {big(yesterday.eaten)} kcal, under the safe
            minimum. Aim for your full {big(today.calorie_goal)} kcal today.
          </span>
        </p>
      )}

      {/* Food from outside the dining halls would otherwise be missing from every number above */}
      <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3">
        <p role="status" className="min-w-0 text-[13px] text-muted">
          {added ? `Added ${added.name}, ${big(added.kcal)} kcal.` : "Ate something that isn't on a dining hall menu?"}
        </p>
        <QuickAddButton
          userId={userId}
          date={todayISO()}
          onAdded={(log) => {
            setAdded(log)
            setVersion((v) => v + 1)
          }}
          className="shrink-0 rounded-lg bg-brand-soft px-3 py-1.5 text-sm font-semibold text-brand-deep transition-colors hover:bg-brand-soft/70"
        />
      </div>
    </Card>
  )
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-xl bg-bg px-2 py-3">
      <p className="text-[12px] font-semibold text-muted">{label}</p>
      <p className="mt-0.5 text-xl font-bold tracking-tight">{value}</p>
      <p className="mt-0.5 text-[11px] leading-tight text-muted">{note}</p>
    </div>
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
