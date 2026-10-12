import { useState } from 'react'
import { createUser, getUser } from '../api'
import { ErrorNote, Field, Input, Select, TagInput } from '../components/ui'
import { ACTIVITY_LEVELS, ALLERGIES, DIETARY_RESTRICTIONS, todayISO } from '../constants'
import { findAccountByEmail, forgetAccount, getAccounts, rememberAccount, setPrefs } from '../session'

const EMPTY_FORM = {
  name: '',
  email: '',
  weight: '',
  heightFt: '',
  heightIn: '',
  sex: '',
  birthdate: '',
  activity: 'light',
  allergies: [],
  diet: [],
  targetWeight: '',
}

export default function AuthPage({ onSignedIn }) {
  const [tab, setTab] = useState(getAccounts().length ? 'login' : 'signup')
  const [prefillEmail, setPrefillEmail] = useState('')

  const goToLogin = (email) => {
    setPrefillEmail(email)
    setTab('login')
  }

  return (
    <section className="grid gap-12 pt-10 pb-24 lg:grid-cols-[1fr_1.1fr] lg:gap-16 lg:pt-16">
      <div className="lg:sticky lg:top-10 lg:self-start">
        <p className="font-mono text-[12px] uppercase tracking-[0.18em] text-illini-deep">For UIUC students and staff</p>
        <h1 className="mt-6 font-serif text-[clamp(2.8rem,6vw,5.6rem)] leading-[0.92] font-medium tracking-[-0.03em]">
          Know what to eat
          <br />
          <em className="font-normal text-illini">before</em> you
          <br />
          reach the dining hall.
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-relaxed text-ink-soft">
          Plate Plan reads today's Illinois dining menus and your body stats, sets daily calorie and macro targets for your goal, and
          shows which dishes fit the meal you're about to eat.
        </p>
        <ol className="mt-10 max-w-md divide-y divide-rule border-y border-ink">
          {['Tell us about yourself', 'Pick a goal: lose, maintain or gain', 'Choose a hall and meal, check off what you eat'].map((s, i) => (
            <li key={s} className="flex gap-4 py-3">
              <span className="font-mono text-illini">0{i + 1}</span>
              {s}
            </li>
          ))}
        </ol>
      </div>

      <div className="border border-ink bg-paper">
        <div className="grid grid-cols-2 border-b border-ink" role="tablist">
          {[
            ['signup', 'Sign up'],
            ['login', 'Log in'],
          ].map(([key, label]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`py-4 font-mono text-[13px] uppercase tracking-wider transition-colors ${
                tab === key ? 'bg-ink text-paper' : 'hover:bg-paper-deep'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="p-6 md:p-8">
          {tab === 'signup' ? (
            <SignUpForm onSignedIn={onSignedIn} onExistingEmail={goToLogin} />
          ) : (
            <LogInForm key={prefillEmail} initialEmail={prefillEmail} onSignedIn={onSignedIn} />
          )}
        </div>
      </div>
    </section>
  )
}

function SignUpForm({ onSignedIn, onExistingEmail }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    const heightIn = Number(form.heightFt) * 12 + Number(form.heightIn || 0)
    if (!form.sex) return setError({ message: 'Please choose your sex; the calorie calculation needs it.' })
    if (heightIn < 36 || heightIn > 96) return setError({ message: 'Please check your height.' })

    setBusy(true)
    try {
      const user = await createUser({
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        weight_lbs: Number(form.weight),
        height_in: heightIn,
        gender: form.sex, // "male" or "female", lowercase
        birthdate: form.birthdate, // YYYY-MM-DD from <input type="date">
        activity_level: form.activity,
        allergies: form.allergies,
        dietary_restrictions: form.diet,
      })
      rememberAccount(user)
      if (form.targetWeight) setPrefs(user.id, { targetWeight: Number(form.targetWeight) })
      onSignedIn(user, { isNew: true })
    } catch (err) {
      setError({ message: err.status === 409 ? 'An account with this email already exists.' : err.message, duplicate: err.status === 409 })
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h2 className="font-serif text-3xl font-medium">Create your plan</h2>
        <p className="mt-1 text-ink-soft">Used to work out your daily calories and to hide dishes you can't eat.</p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name">
          <Input required value={form.name} onChange={set('name')} autoComplete="name" />
        </Field>
        <Field label="Email">
          <Input required type="email" value={form.email} onChange={set('email')} autoComplete="email" />
        </Field>

        <Field label="Weight (lb)">
          <Input required type="number" inputMode="decimal" min="50" max="700" step="0.1" value={form.weight} onChange={set('weight')} />
        </Field>
        <Field label="Height">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input required type="number" inputMode="numeric" min="3" max="8" step="1" value={form.heightFt} onChange={set('heightFt')} aria-label="Height, feet" className="pr-8" />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 font-mono text-sm text-ink-soft">ft</span>
            </div>
            <div className="relative flex-1">
              <Input type="number" inputMode="decimal" min="0" max="11.9" step="0.5" value={form.heightIn} onChange={set('heightIn')} aria-label="Height, inches" className="pr-8" />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 font-mono text-sm text-ink-soft">in</span>
            </div>
          </div>
        </Field>

        <Field label="Sex" hint="Used in the calorie calculation.">
          <Select required value={form.sex} onChange={set('sex')}>
            <option value="" disabled>
              Choose…
            </option>
            <option value="female">Female</option>
            <option value="male">Male</option>
          </Select>
        </Field>
        <Field label="Birthday">
          <Input required type="date" min="1900-01-01" max={todayISO()} value={form.birthdate} onChange={set('birthdate')} />
        </Field>

        <Field label="How often do you exercise?" className="sm:col-span-2">
          <Select required value={form.activity} onChange={set('activity')}>
            {ACTIVITY_LEVELS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="space-y-5 border-t border-rule pt-5">
        <div>
          <label htmlFor="allergies" className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">
            Allergies
          </label>
          <div className="mt-1.5">
            <TagInput
              id="allergies"
              options={ALLERGIES}
              value={form.allergies}
              onChange={(allergies) => setForm((f) => ({ ...f, allergies }))}
              placeholder="Type an allergy, e.g. peanuts"
            />
          </div>
        </div>
        <div>
          <label htmlFor="diet" className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">
            Dietary restrictions
          </label>
          <div className="mt-1.5">
            <TagInput
              id="diet"
              options={DIETARY_RESTRICTIONS}
              value={form.diet}
              onChange={(diet) => setForm((f) => ({ ...f, diet }))}
              placeholder="Type a restriction, e.g. vegetarian"
            />
          </div>
        </div>
      </div>

      <div className="border-t border-rule pt-5">
        <Field label="Target weight (lb, optional)" hint="Shown on your progress chart.">
          <Input type="number" inputMode="decimal" min="50" max="700" step="0.1" value={form.targetWeight} onChange={set('targetWeight')} className="sm:max-w-[50%]" />
        </Field>
      </div>

      {error && (
        <ErrorNote>
          {error.message}{' '}
          {error.duplicate && (
            <button type="button" onClick={() => onExistingEmail(form.email.trim())} className="font-medium underline">
              Log in instead
            </button>
          )}
        </ErrorNote>
      )}

      <button
        disabled={busy}
        className="w-full bg-ink px-6 py-3.5 text-[15px] font-medium text-paper transition-colors hover:bg-illini disabled:opacity-60"
      >
        {busy ? 'Creating your plan…' : 'Sign up'}
      </button>
    </form>
  )
}

function LogInForm({ initialEmail, onSignedIn }) {
  const [email, setEmail] = useState(initialEmail)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [accounts, setAccounts] = useState(getAccounts)

  const logIn = async (account) => {
    setError('')
    setBusy(true)
    try {
      const user = await getUser(account.id)
      // A reset database can reuse ids, so make sure the id still belongs to this email
      if (user.email.toLowerCase() !== account.email.toLowerCase()) throw Object.assign(new Error(), { status: 404 })
      rememberAccount(user)
      onSignedIn(user, { isNew: false })
    } catch (err) {
      if (err.status === 404) {
        forgetAccount(account.id)
        setAccounts(getAccounts())
        setError('That account no longer exists on the server. Please sign up again.')
      } else {
        setError(err.message)
      }
      setBusy(false)
    }
  }

  const submit = (e) => {
    e.preventDefault()
    const account = findAccountByEmail(email)
    if (!account) {
      setError(
        "No account with that email has signed up in this browser. Logging in from another browser isn't available yet, so sign up here instead.",
      )
      return
    }
    logIn(account)
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h2 className="font-serif text-3xl font-medium">Welcome back</h2>
        <p className="mt-1 text-ink-soft">Accounts are remembered in this browser until full login is added.</p>
      </div>

      {accounts.length > 0 && (
        <ul className="divide-y divide-rule border-y border-ink">
          {accounts.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                disabled={busy}
                onClick={() => logIn(a)}
                className="flex w-full items-center justify-between gap-4 py-3 text-left transition-colors hover:text-illini-deep disabled:opacity-60"
              >
                <span>
                  <span className="font-medium">{a.name}</span>
                  <span className="ml-2 font-mono text-[13px] text-ink-soft">{a.email}</span>
                </span>
                <span className="font-mono text-[12px] uppercase tracking-wider">Continue →</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Field label="Email">
        <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
      </Field>

      <ErrorNote>{error}</ErrorNote>

      <button
        disabled={busy}
        className="w-full bg-ink px-6 py-3.5 text-[15px] font-medium text-paper transition-colors hover:bg-illini disabled:opacity-60"
      >
        {busy ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  )
}
