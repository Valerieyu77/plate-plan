import { useState } from 'react'
import { createUser, getUser } from '../api'
import { Button, Card, ErrorNote, Field, Input, Segmented, Select, TagInput } from '../components/ui'
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
    <section>
      <div className="pt-4 pb-6">
        <p className="text-[13px] font-semibold text-brand">For UIUC students and staff</p>
        <h1 className="mt-2 text-[2rem] leading-tight font-bold tracking-tight">Know what to eat before you reach the dining hall.</h1>
        <p className="mt-3 text-muted">
          Plate Plan reads today's Illinois dining menus, sets calorie and macro targets for your goal, and shows which dishes fit your next meal.
        </p>
        <ol className="no-scrollbar -mx-4 mt-5 flex gap-2 overflow-x-auto px-4">
          {['Tell us about yourself', 'Pick a goal', 'Plan each meal'].map((step, i) => (
            <li key={step} className="flex shrink-0 items-center gap-2 rounded-full bg-surface py-1.5 pr-3.5 pl-1.5 text-sm font-medium ring-1 ring-line">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-soft text-[12px] font-bold text-brand-deep">{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </div>

      <Card>
        <Segmented
          options={[
            ['signup', 'Sign up'],
            ['login', 'Log in'],
          ]}
          value={tab}
          onChange={setTab}
        />
        <div className="mt-5">
          {tab === 'signup' ? (
            <SignUpForm onSignedIn={onSignedIn} onExistingEmail={goToLogin} />
          ) : (
            <LogInForm key={prefillEmail} initialEmail={prefillEmail} onSignedIn={onSignedIn} />
          )}
        </div>
      </Card>

      <p className="mt-6 text-center text-[13px] text-muted">Menus from UIUC Dining · Built for the University of Illinois Urbana-Champaign</p>
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
        <h2 className="text-xl font-bold">Create your plan</h2>
        <p className="mt-1 text-sm text-muted">Used to work out your daily calories and to hide dishes you can't eat.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Name" className="col-span-2">
          <Input required value={form.name} onChange={set('name')} autoComplete="name" />
        </Field>
        <Field label="Email" className="col-span-2">
          <Input required type="email" value={form.email} onChange={set('email')} autoComplete="email" />
        </Field>

        <Field label="Weight (lb)">
          <Input required type="number" inputMode="decimal" min="50" max="700" step="0.1" value={form.weight} onChange={set('weight')} />
        </Field>
        <Field label="Height">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input required type="number" inputMode="numeric" min="3" max="8" step="1" value={form.heightFt} onChange={set('heightFt')} aria-label="Height, feet" className="pr-8" />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted">ft</span>
            </div>
            <div className="relative flex-1">
              <Input type="number" inputMode="decimal" min="0" max="11.9" step="0.5" value={form.heightIn} onChange={set('heightIn')} aria-label="Height, inches" className="pr-8" />
              <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted">in</span>
            </div>
          </div>
        </Field>

        <Field label="Sex">
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

        <Field label="How often do you exercise?" className="col-span-2">
          <Select required value={form.activity} onChange={set('activity')}>
            {ACTIVITY_LEVELS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="space-y-5 border-t border-line pt-5">
        <div>
          <label htmlFor="allergies" className="text-[13px] font-semibold text-muted">
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
          <label htmlFor="diet" className="text-[13px] font-semibold text-muted">
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

      <div className="border-t border-line pt-5">
        <Field label="Target weight (lb, optional)" hint="Shown on your progress chart.">
          <Input type="number" inputMode="decimal" min="50" max="700" step="0.1" value={form.targetWeight} onChange={set('targetWeight')}  />
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

      <Button disabled={busy} className="w-full">
        {busy ? 'Creating your plan…' : 'Sign up'}
      </Button>
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
        <h2 className="text-xl font-bold">Welcome back</h2>
        <p className="mt-1 text-sm text-muted">Accounts are remembered in this browser until full login is added.</p>
      </div>

      {accounts.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-xl ring-1 ring-line">
          {accounts.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                disabled={busy}
                onClick={() => logIn(a)}
                className="flex w-full items-center gap-3 px-3.5 py-3 text-left transition-colors hover:bg-bg disabled:opacity-60"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-sm font-semibold text-white">
                  {a.name.trim().charAt(0).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{a.name}</span>
                  <span className="block truncate text-[13px] text-muted">{a.email}</span>
                </span>
                <span className="text-sm font-semibold text-brand">Continue</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Field label="Email">
        <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
      </Field>

      <ErrorNote>{error}</ErrorNote>

      <Button disabled={busy} className="w-full">
        {busy ? 'Logging in…' : 'Log in'}
      </Button>
    </form>
  )
}
