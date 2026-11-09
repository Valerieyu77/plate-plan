import { useState } from 'react'
import { logIn, signUp } from '../api'
import { Button, Card, ErrorNote, Field, Input, PageHeader, Segmented, Select, TagInput } from '../components/ui'
import { ACTIVITY_LEVELS, ALLERGIES, DIETARY_RESTRICTIONS } from '../constants'
import { getLastEmail } from '../session'

const EMPTY_FORM = {
  name: '',
  email: '',
  password: '',
  weight: '',
  heightFt: '',
  heightIn: '',
  sex: '',
  birthdate: '',
  activity: 'light',
  allergies: [],
  diet: [],
}

// The calorie formula (Mifflin-St Jeor) is made for adults; children and young teens need a doctor's advice instead.
// The backend refuses younger sign-ups too (MIN_AGE in app/nutrition.py, keep in sync).
const MIN_AGE = 16

// The latest birthday allowed: MIN_AGE years before today, local time (Feb 29 becomes Feb 28)
function latestBirthdate() {
  const d = new Date()
  const year = d.getFullYear() - MIN_AGE
  const day = Math.min(d.getDate(), new Date(year, d.getMonth() + 1, 0).getDate())
  return `${year}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export default function AuthPage({ onSignedIn, initialTab }) {
  const [tab, setTab] = useState(initialTab || (getLastEmail() ? 'login' : 'signup'))
  const [prefillEmail, setPrefillEmail] = useState(getLastEmail)

  const goToLogin = (email) => {
    setPrefillEmail(email)
    setTab('login')
  }

  return (
    <section>
      <PageHeader
        title="Welcome to Plate Plan"
        sub="Sign up to get your daily targets and meal plans, or log in to pick up where you left off."
      />

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
    // The date field's max catches this too, but not every browser checks typed dates
    if (form.birthdate > latestBirthdate()) return setError({ message: `Plate Plan is for people ${MIN_AGE} and older.` })
    if (form.password.length < 8) return setError({ message: 'Please use a password of at least 8 characters.' })

    setBusy(true)
    try {
      const auth = await signUp({
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        weight_lbs: Number(form.weight),
        height_in: heightIn,
        gender: form.sex, // "male" or "female", lowercase
        birthdate: form.birthdate, // YYYY-MM-DD from <input type="date">
        activity_level: form.activity,
        allergies: form.allergies,
        dietary_restrictions: form.diet,
      })
      onSignedIn(auth, { isNew: true })
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
        <Field label="Password" hint="At least 8 characters." className="col-span-2">
          <Input required type="password" minLength={8} maxLength={72} value={form.password} onChange={set('password')} autoComplete="new-password" />
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
        <Field label="Birthday" hint={`You must be ${MIN_AGE} or older.`}>
          <Input required type="date" min="1900-01-01" max={latestBirthdate()} value={form.birthdate} onChange={set('birthdate')} />
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
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      onSignedIn(await logIn(email.trim().toLowerCase(), password), { isNew: false })
    } catch (err) {
      setError(err.status === 401 ? 'Incorrect email or password.' : err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Welcome back</h2>
        <p className="mt-1 text-sm text-muted">Log in on any device with your email and password.</p>
      </div>

      <Field label="Email">
        <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
      </Field>
      <Field label="Password">
        <Input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
      </Field>

      <ErrorNote>{error}</ErrorNote>

      <Button disabled={busy} className="w-full">
        {busy ? 'Logging in…' : 'Log in'}
      </Button>
    </form>
  )
}
