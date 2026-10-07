import { useState } from 'react'

const GOALS = {
  lose: { label: 'Lose weight', note: '−450 kcal deficit, high protein', cal: 1900, p: 150, c: 190, f: 60 },
  maintain: { label: 'Maintain', note: 'Balanced intake', cal: 2350, p: 120, c: 290, f: 75 },
  gain: { label: 'Gain muscle', note: '+400 kcal surplus', cal: 2850, p: 165, c: 350, f: 88 },
}

const MICROS = ['Iron', 'Calcium', 'Vitamin D', 'Vitamin C', 'Fiber', 'B12']

// Sample menu data until the backend menu API is wired up
const HALLS = {
  'Ikenberry (IKE)': {
    tag: 'Dinner · until 8:00 pm',
    open: 'Open',
    items: [
      { id: 'i1', name: 'Herb-roasted chicken thigh', cal: 340, p: 34, c: 2, f: 21, micros: ['B12'] },
      { id: 'i2', name: 'Brown rice pilaf', cal: 210, p: 5, c: 42, f: 3, micros: ['Fiber'] },
      { id: 'i3', name: 'Garlic broccoli', cal: 70, p: 5, c: 12, f: 1, micros: ['Vitamin C', 'Fiber'] },
      { id: 'i4', name: 'Baked salmon, lemon dill', cal: 290, p: 31, c: 1, f: 18, micros: ['Vitamin D', 'B12'] },
      { id: 'i5', name: 'Cheese pizza slice', cal: 310, p: 13, c: 36, f: 12, micros: ['Calcium'] },
    ],
  },
  'Illinois Street (ISR)': {
    tag: 'Dinner · until 9:00 pm',
    open: 'Open',
    items: [
      { id: 's1', name: 'Grilled flank steak', cal: 310, p: 36, c: 1, f: 17, micros: ['Iron', 'B12'] },
      { id: 's2', name: 'Black bean burrito bowl', cal: 480, p: 20, c: 72, f: 12, micros: ['Iron', 'Fiber'] },
      { id: 's3', name: 'Spinach and kale salad', cal: 90, p: 4, c: 10, f: 4, micros: ['Iron', 'Vitamin C'] },
      { id: 's4', name: 'Greek yogurt parfait', cal: 220, p: 17, c: 28, f: 5, micros: ['Calcium', 'Vitamin D'] },
      { id: 's5', name: 'Mac and cheese', cal: 420, p: 15, c: 48, f: 19, micros: ['Calcium'] },
    ],
  },
  'Pennsylvania Ave (PAR)': {
    tag: 'Dinner · until 8:30 pm',
    open: 'Open',
    items: [
      { id: 'p1', name: 'Tofu and veggie stir-fry', cal: 330, p: 22, c: 30, f: 14, micros: ['Iron', 'Vitamin C', 'Calcium'] },
      { id: 'p2', name: 'Turkey meatballs', cal: 260, p: 28, c: 8, f: 13, micros: ['B12'] },
      { id: 'p3', name: 'Sweet potato wedges', cal: 180, p: 3, c: 38, f: 3, micros: ['Vitamin C', 'Fiber'] },
      { id: 'p4', name: 'Fortified oat milk cereal bowl', cal: 250, p: 8, c: 44, f: 5, micros: ['Vitamin D', 'Calcium', 'Iron'] },
      { id: 'p5', name: 'Chocolate chip cookie', cal: 220, p: 2, c: 30, f: 11, micros: [] },
    ],
  },
  'Lincoln Ave (LAR)': {
    tag: 'Dinner · until 8:00 pm',
    open: 'Open',
    items: [
      { id: 'l1', name: 'Lentil and veggie curry', cal: 310, p: 16, c: 46, f: 8, micros: ['Iron', 'Fiber'] },
      { id: 'l2', name: 'Grilled tilapia', cal: 200, p: 34, c: 0, f: 6, micros: ['B12'] },
      { id: 'l3', name: 'Orange and berry fruit cup', cal: 90, p: 1, c: 22, f: 0, micros: ['Vitamin C', 'Fiber'] },
      { id: 'l4', name: 'Scrambled eggs, 2 ct', cal: 180, p: 12, c: 2, f: 14, micros: ['Vitamin D', 'B12'] },
      { id: 'l5', name: 'Fried chicken sandwich', cal: 540, p: 28, c: 48, f: 26, micros: [] },
    ],
  },
}

const SEED = [
  { id: 'seed1', name: 'Oatmeal with banana · breakfast', cal: 320, p: 10, c: 60, f: 6, micros: ['Fiber'] },
  { id: 'seed2', name: 'Chicken wrap · lunch', cal: 560, p: 34, c: 52, f: 22, micros: ['B12'] },
]

function Bar({ label, value, max, unit, strong }) {
  const pct = Math.min(100, (value / max) * 100)
  const over = value > max
  return (
    <div>
      <div className="flex items-baseline justify-between font-mono text-[12px] uppercase tracking-wider">
        <span className="text-ink-soft">{label}</span>
        <span className={over ? 'text-illini-deep' : 'text-ink'}>
          {Math.round(value)} / {max}
          {unit}
        </span>
      </div>
      <div className="mt-1.5 h-[6px] w-full bg-paper-deep">
        <div
          className={`h-full transition-all duration-500 ${strong ? 'bg-illini' : 'bg-ink'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function SectionHead({ n, title, sub }) {
  return (
    <div className="mb-10 grid gap-3 border-t border-ink pt-5 md:grid-cols-[120px_1fr_1fr] md:gap-8">
      <span className="font-mono text-sm text-illini-deep">{n}</span>
      <h2 className="font-serif text-4xl leading-none font-medium tracking-tight md:text-5xl">{title}</h2>
      <p className="max-w-md text-ink-soft md:justify-self-end">{sub}</p>
    </div>
  )
}

export default function App() {
  const [goal, setGoal] = useState('lose')
  const [hall, setHall] = useState('Ikenberry (IKE)')
  const [log, setLog] = useState(SEED)
  const [temp, setTemp] = useState(86)
  const [humidity, setHumidity] = useState(68)
  const [workoutMin, setWorkoutMin] = useState(45)
  const [weight, setWeight] = useState(165)
  const [custom, setCustom] = useState({ name: '', cal: '' })

  const t = GOALS[goal]
  const totals = log.reduce((a, i) => ({ cal: a.cal + i.cal, p: a.p + i.p, c: a.c + i.c, f: a.f + i.f }), { cal: 0, p: 0, c: 0, f: 0 })
  const covered = new Set(log.flatMap((i) => i.micros))
  const missing = MICROS.filter((m) => !covered.has(m))
  const remaining = Math.max(0, t.cal - totals.cal)

  const target = Math.min(remaining, 750)
  const pDensity = goal === 'maintain' ? 0.06 : 0.08
  const ranked = HALLS[hall].items
    .map((i) => {
      const microHits = i.micros.filter((m) => missing.includes(m))
      const calFit = 1 - Math.abs(i.cal - target / 3) / Math.max(target, 300)
      const score = calFit + (i.p / Math.max(i.cal, 1)) / pDensity * 0.6 + microHits.length * 0.45 - (goal === 'lose' && i.f / i.cal > 0.045 ? 0.3 : 0)
      return { item: i, microHits, score }
    })
    .sort((a, b) => b.score - a.score)

  const picks = ranked.slice(0, 3)
  const pickTotals = picks.reduce((a, r) => ({ cal: a.cal + r.item.cal, p: a.p + r.item.p }), { cal: 0, p: 0 })

  const heatFactor = temp >= 90 ? 1.4 : temp >= 80 ? 1.25 : temp >= 70 ? 1.1 : 1
  const humidFactor = humidity >= 70 ? 1.1 : 1
  const baseOz = weight * 0.5
  const workoutOz = (workoutMin / 30) * 8 * heatFactor * humidFactor
  const totalOz = Math.round(baseOz + workoutOz)
  const sodium = Math.round((workoutMin / 30) * 300 * heatFactor * humidFactor)
  const potassium = Math.round(sodium * 0.3)

  const add = (i) => setLog((l) => [...l, { ...i, id: i.id + '-' + Date.now() + Math.random() }])

  const addCustom = () => {
    const cal = parseInt(custom.cal)
    if (!custom.name.trim() || !cal) return
    setLog((l) => [...l, { id: 'c' + Date.now(), name: custom.name.trim(), cal, p: 0, c: 0, f: 0, micros: [] }])
    setCustom({ name: '', cal: '' })
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1240px] px-6 md:px-10">
        <header className="flex items-center justify-between py-6">
          <a href="#top" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center bg-illini font-serif text-lg font-semibold text-white">I</span>
            <span className="font-serif text-xl font-medium tracking-tight">Plate Plan</span>
          </a>
          <nav className="hidden gap-8 font-mono text-[12px] uppercase tracking-wider md:flex">
            {[
              ['#recommend', 'Recommend'],
              ['#log', 'Log'],
              ['#hydrate', 'Hydrate'],
              ['#roadmap', 'Roadmap'],
            ].map(([h, l]) => (
              <a key={h} href={h} className="text-ink-soft transition-colors hover:text-illini-deep">
                {l}
              </a>
            ))}
          </nav>
        </header>

        <section id="top" className="grid gap-12 pt-12 pb-24 lg:grid-cols-[1.35fr_1fr] lg:gap-16 lg:pt-20">
          <div>
            <p className="font-mono text-[12px] uppercase tracking-[0.18em] text-illini-deep">For UIUC students and staff</p>
            <h1 className="mt-6 font-serif text-[clamp(3rem,7.4vw,6.6rem)] leading-[0.92] font-medium tracking-[-0.03em]">
              Know what to eat
              <br />
              <em className="font-normal text-illini">before</em> you
              <br />
              reach the dining hall.
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-relaxed text-ink-soft">
              Plate Plan reads tonight's Illinois dining menus, your Strava or Garmin workouts, and Champaign weather. Then it tells you what to put on your tray and how much to drink.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <a href="#recommend" className="bg-ink px-6 py-3.5 text-[15px] font-medium text-paper transition-colors hover:bg-illini">
                Plan tonight's plate
              </a>
              <a href="#hydrate" className="border border-ink px-6 py-3.5 text-[15px] font-medium transition-colors hover:bg-ink hover:text-paper">
                Check my hydration
              </a>
            </div>
          </div>

          <aside className="self-end border border-ink bg-paper-deep/60 p-6">
            <div className="flex items-center justify-between font-mono text-[12px] uppercase tracking-wider text-ink-soft">
              <span>Today · Champaign, IL</span>
              <span>4:52 pm</span>
            </div>
            <div className="mt-4 flex items-end gap-6 border-b border-rule pb-5">
              <span className="font-serif text-7xl leading-none font-medium">{temp}°</span>
              <span className="pb-2 font-mono text-sm text-ink-soft">
                {humidity}% humidity
                <br />
                feels {temp + Math.round((humidity - 40) / 10)}°F
              </span>
            </div>
            <dl className="mt-5 space-y-3 text-[15px]">
              <div className="flex justify-between">
                <dt className="text-ink-soft">Strava · run, 5.1 km</dt>
                <dd className="font-mono">{workoutMin} min</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-soft">Calories left</dt>
                <dd className="font-mono">{remaining} kcal</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-soft">Drink today</dt>
                <dd className="font-mono text-illini-deep">{totalOz} oz</dd>
              </div>
            </dl>
          </aside>
        </section>

        <section className="pb-20">
          <div className="grid gap-px border border-ink bg-ink md:grid-cols-3">
            {Object.keys(GOALS).map((g) => (
              <button
                key={g}
                onClick={() => setGoal(g)}
                aria-pressed={goal === g}
                className={`p-6 text-left transition-colors ${goal === g ? 'bg-ink text-paper' : 'bg-paper hover:bg-paper-deep'}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-serif text-2xl font-medium">{GOALS[g].label}</span>
                  <span className={`font-mono text-[11px] uppercase tracking-wider ${goal === g ? 'text-illini' : 'text-ink-soft'}`}>
                    {goal === g ? '● Your goal' : 'Select'}
                  </span>
                </div>
                <p className={`mt-1 text-sm ${goal === g ? 'text-paper/70' : 'text-ink-soft'}`}>{GOALS[g].note}</p>
                <p className="mt-4 font-mono text-sm">
                  {GOALS[g].cal} kcal · {GOALS[g].p}P {GOALS[g].c}C {GOALS[g].f}F
                </p>
              </button>
            ))}
          </div>
        </section>

        <section id="recommend" className="scroll-mt-6 pb-28">
          <SectionHead
            n="01"
            title="Tonight's recommendation"
            sub="Ranked against what you have left today and the vitamins your log is missing."
          />
          <div className="mb-8 flex flex-wrap gap-2">
            {Object.keys(HALLS).map((h) => (
              <button
                key={h}
                onClick={() => setHall(h)}
                aria-pressed={hall === h}
                className={`border border-ink px-4 py-2 font-mono text-[12px] uppercase tracking-wider transition-colors ${hall === h ? 'bg-ink text-paper' : 'hover:bg-paper-deep'}`}
              >
                {h}
              </button>
            ))}
          </div>

          <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr]">
            <div className="border border-ink bg-ink p-7 text-paper">
              <p className="font-mono text-[12px] uppercase tracking-wider text-illini">{HALLS[hall].tag}</p>
              <h3 className="mt-3 font-serif text-3xl leading-tight font-medium">Your tray, in three picks</h3>
              <ol className="mt-6 space-y-4">
                {picks.map((r, idx) => (
                  <li key={r.item.id} className="flex gap-4 border-t border-paper/20 pt-4">
                    <span className="font-mono text-illini">0{idx + 1}</span>
                    <div>
                      <p className="font-medium">{r.item.name}</p>
                      <p className="font-mono text-[12px] text-paper/60">
                        {r.item.cal} kcal · {r.item.p}g protein
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="mt-6 flex items-end justify-between border-t border-paper/20 pt-5">
                <p className="font-mono text-sm text-paper/70">
                  {pickTotals.cal} kcal · {pickTotals.p}g protein
                </p>
                <button
                  onClick={() => picks.forEach((r) => add(r.item))}
                  className="bg-illini px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-illini-deep"
                >
                  Log all three
                </button>
              </div>
              <p className="mt-5 text-sm text-paper/60">
                Missing from today's log: {missing.length ? missing.join(', ') : 'nothing, nicely done.'}
              </p>
            </div>

            <ul className="divide-y divide-rule border-y border-ink">
              {ranked.map((r) => (
                <li key={r.item.id} className="group flex items-center gap-4 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-serif text-xl font-medium">{r.item.name}</p>
                    <p className="mt-0.5 font-mono text-[12px] text-ink-soft">
                      {r.item.cal} kcal · {r.item.p}P {r.item.c}C {r.item.f}F
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {r.item.micros.map((m) => (
                        <span
                          key={m}
                          className={`px-2 py-0.5 font-mono text-[11px] uppercase ${
                            r.microHits.includes(m) ? 'bg-illini text-white' : 'border border-rule text-ink-soft'
                          }`}
                        >
                          {r.microHits.includes(m) ? `+ ${m}` : m}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => add(r.item)}
                    aria-label={`Add ${r.item.name}`}
                    className="grid h-10 w-10 shrink-0 place-items-center border border-ink text-xl transition-colors hover:bg-ink hover:text-paper"
                  >
                    +
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="log" className="scroll-mt-6 pb-28">
          <SectionHead n="02" title="Calorie counter" sub="Everything you've eaten today, measured against your goal." />
          <div className="grid gap-12 lg:grid-cols-2">
            <div>
              <div className="flex items-end gap-4">
                <span className="font-serif text-8xl leading-none font-medium tracking-tight">{Math.round(totals.cal)}</span>
                <span className="pb-3 font-mono text-sm text-ink-soft">
                  of {t.cal} kcal
                  <br />
                  <span className={totals.cal > t.cal ? 'text-illini-deep' : ''}>
                    {totals.cal > t.cal ? `${totals.cal - t.cal} over` : `${remaining} left`}
                  </span>
                </span>
              </div>
              <div className="mt-8 space-y-5">
                <Bar label="Calories" value={totals.cal} max={t.cal} unit="" strong />
                <Bar label="Protein" value={totals.p} max={t.p} unit="g" />
                <Bar label="Carbs" value={totals.c} max={t.c} unit="g" />
                <Bar label="Fat" value={totals.f} max={t.f} unit="g" />
              </div>
            </div>

            <div>
              <ul className="divide-y divide-rule border-y border-ink">
                {log.length === 0 && <li className="py-6 text-ink-soft">Nothing logged yet. Add from the menu above.</li>}
                {log.map((i) => (
                  <li key={i.id} className="flex items-center justify-between gap-4 py-3">
                    <span className="truncate">{i.name}</span>
                    <span className="flex items-center gap-4">
                      <span className="font-mono text-sm">{i.cal}</span>
                      <button
                        onClick={() => setLog((l) => l.filter((x) => x.id !== i.id))}
                        aria-label={`Remove ${i.name}`}
                        className="font-mono text-ink-soft transition-colors hover:text-illini-deep"
                      >
                        ✕
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-5 flex gap-2">
                <input
                  value={custom.name}
                  onChange={(e) => setCustom({ ...custom, name: e.target.value })}
                  placeholder="Add something else"
                  className="min-w-0 flex-1 border border-ink bg-transparent px-3 py-2.5 placeholder:text-ink-soft/70"
                />
                <input
                  value={custom.cal}
                  onChange={(e) => setCustom({ ...custom, cal: e.target.value.replace(/\D/g, '') })}
                  onKeyDown={(e) => e.key === 'Enter' && addCustom()}
                  placeholder="kcal"
                  inputMode="numeric"
                  className="w-20 border border-ink bg-transparent px-3 py-2.5 font-mono placeholder:text-ink-soft/70"
                />
                <button onClick={addCustom} className="bg-ink px-4 text-sm font-medium text-paper transition-colors hover:bg-illini">
                  Add
                </button>
              </div>
            </div>
          </div>
        </section>

        <section id="hydrate" className="scroll-mt-6 pb-28">
          <SectionHead n="03" title="Water and electrolytes" sub="Your workout, today's heat and humidity, and your body weight set the target." />
          <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr]">
            <div className="space-y-7">
              {[
                { l: 'Workout length', v: workoutMin, set: setWorkoutMin, min: 0, max: 150, step: 5, u: ' min' },
                { l: 'Temperature', v: temp, set: setTemp, min: 30, max: 105, step: 1, u: '°F' },
                { l: 'Humidity', v: humidity, set: setHumidity, min: 10, max: 100, step: 1, u: '%' },
                { l: 'Body weight', v: weight, set: setWeight, min: 90, max: 280, step: 1, u: ' lb' },
              ].map((s) => (
                <label key={s.l} className="block">
                  <span className="flex justify-between font-mono text-[12px] uppercase tracking-wider">
                    <span className="text-ink-soft">{s.l}</span>
                    <span>
                      {s.v}
                      {s.u}
                    </span>
                  </span>
                  <input
                    type="range"
                    min={s.min}
                    max={s.max}
                    step={s.step}
                    value={s.v}
                    onChange={(e) => s.set(+e.target.value)}
                    className="mt-2 w-full"
                  />
                </label>
              ))}
            </div>

            <div className="grid gap-px self-start border border-ink bg-ink sm:grid-cols-3">
              {[
                { l: 'Water today', v: totalOz, u: 'oz', s: `${(totalOz * 0.0296).toFixed(1)} L total`, hi: true },
                { l: 'Sodium', v: sodium, u: 'mg', s: 'around your workout' },
                { l: 'Potassium', v: potassium, u: 'mg', s: 'with your post-run meal' },
              ].map((c) => (
                <div key={c.l} className={`p-6 ${c.hi ? 'bg-illini text-white' : 'bg-paper'}`}>
                  <p className={`font-mono text-[12px] uppercase tracking-wider ${c.hi ? 'text-white/80' : 'text-ink-soft'}`}>{c.l}</p>
                  <p className="mt-6 font-serif text-6xl leading-none font-medium">
                    {c.v}
                    <span className="ml-1 font-mono text-base">{c.u}</span>
                  </p>
                  <p className={`mt-3 text-sm ${c.hi ? 'text-white/85' : 'text-ink-soft'}`}>{c.s}</p>
                </div>
              ))}
              <p className="bg-paper p-6 text-ink-soft sm:col-span-3">
                {heatFactor > 1.2
                  ? 'Heat is pushing your needs up. Sip 6–8 oz every 20 minutes during exercise, and add an electrolyte tab to your bottle.'
                  : 'Mild conditions. Water alone is enough for most of this workout; salt your post-run meal.'}
              </p>
            </div>
          </div>
        </section>

        <section id="roadmap" className="scroll-mt-6 pb-28">
          <SectionHead n="04" title="What's next" sub="The MVP is this page. Here is where it goes by the end of the semester and beyond." />
          <div className="grid gap-12 md:grid-cols-2">
            <div>
              <h3 className="mb-4 font-mono text-[12px] uppercase tracking-wider text-illini-deep">MVP · this semester</h3>
              <ul className="divide-y divide-rule border-y border-ink">
                {['Recommendations from calories, macros, water and your goal', 'Calorie counter with daily targets', 'Illinois dining menu data', 'Strava and Garmin workouts, local weather'].map((x) => (
                  <li key={x} className="flex gap-3 py-3">
                    <span className="font-mono text-illini">✓</span>
                    {x}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-4 font-mono text-[12px] uppercase tracking-wider text-ink-soft">Later</h3>
              <ul className="divide-y divide-rule border-y border-ink">
                {['Campus eateries beyond the dining halls', 'Home-cooked meals and recipes', 'Plans tied to specific training goals'].map((x) => (
                  <li key={x} className="flex gap-3 py-3">
                    <span className="font-mono text-ink-soft">○</span>
                    {x}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <footer className="flex flex-col justify-between gap-2 border-t border-ink py-8 font-mono text-[12px] uppercase tracking-wider text-ink-soft md:flex-row">
          <span>Plate Plan · Built for the University of Illinois Urbana-Champaign</span>
          <span>Sample data for demonstration</span>
        </footer>
      </div>
    </div>
  )
}
