import { useEffect, useState } from 'react'
import { changePassword, deleteAccount, getUser, updateProfile } from '../api'
import { Button, Card, ErrorNote, Field, Input, Loading, PageHeader, Select, TagInput } from '../components/ui'
import { ACTIVITY_LEVELS, ALLERGIES, DIETARY_RESTRICTIONS, MIN_AGE, latestBirthdate } from '../constants'
import { forgetUser } from '../session'

// What the goal's daily targets are calculated from: changing one of these recalculates them (PATCH /users/{id})
const TARGET_FIELDS = ['height_in', 'gender', 'birthdate', 'activity_level']

// The user from the API -> the form's fields (height split into feet and inches, like the sign-up form)
function toForm(u) {
  const height = u.height_in || 0
  const feet = Math.floor(height / 12)
  return {
    name: u.name || '',
    heightFt: height ? String(feet) : '',
    heightIn: height ? String(Math.round((height - feet * 12) * 10) / 10) : '',
    sex: u.gender || '',
    birthdate: u.birthdate || '',
    activity: u.activity_level || 'light',
    allergies: u.allergies || [],
    diet: u.dietary_restrictions || [],
  }
}

const sameList = (a = [], b = []) => [...a].sort().join('|') === [...b].sort().join('|')

// Only what changed, in the API's names: PATCH /users/{id} takes just those
function changesFrom(form, u) {
  const height = Number(form.heightFt) * 12 + Number(form.heightIn || 0)
  const changes = {}
  if (form.name.trim() !== u.name) changes.name = form.name.trim()
  if (Math.abs(height - (u.height_in || 0)) > 0.01) changes.height_in = height
  if (form.sex !== (u.gender || '')) changes.gender = form.sex
  if (form.birthdate !== (u.birthdate || '')) changes.birthdate = form.birthdate
  if (form.activity !== (u.activity_level || 'light')) changes.activity_level = form.activity
  if (!sameList(form.allergies, u.allergies)) changes.allergies = form.allergies
  if (!sameList(form.diet, u.dietary_restrictions)) changes.dietary_restrictions = form.diet
  return changes
}

export default function SettingsPage({ user, onUserChange, onDeleted }) {
  // The login copy can be old (weigh-ins change the weight), so load the profile fresh
  const [profile, setProfile] = useState(null)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let ignore = false
    getUser(user.id)
      .then((u) => !ignore && setProfile(u))
      .catch((err) => !ignore && setLoadError(err.message))
    return () => {
      ignore = true
    }
  }, [user.id])

  const saved = (u) => {
    setProfile(u)
    onUserChange(u)
  }

  return (
    <section>
      <PageHeader title="Settings" sub={`Signed in as ${user.email}`} />
      {loadError ? (
        <ErrorNote>{loadError}</ErrorNote>
      ) : !profile ? (
        <Loading />
      ) : (
        <div className="space-y-4">
          <ProfileCard profile={profile} onSaved={saved} />
          <PasswordCard />
          <DeleteCard user={user} onDeleted={onDeleted} />
        </div>
      )}
    </section>
  )
}

function ProfileCard({ profile, onSaved }) {
  const [form, setForm] = useState(() => toForm(profile))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setDone('')
  }
  const changes = changesFrom(form, profile)
  const changed = Object.keys(changes).length > 0

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setDone('')
    const height = Number(form.heightFt) * 12 + Number(form.heightIn || 0)
    if (!form.name.trim()) return setError('Please enter your name.')
    if (height < 36 || height > 96) return setError('Please check your height.')
    if (form.birthdate > latestBirthdate()) return setError(`Plate Plan is for people ${MIN_AGE} and older.`)
    setBusy(true)
    try {
      const u = await updateProfile(profile.id, changes)
      onSaved(u)
      setForm(toForm(u)) // what the server kept, e.g. a cleaned-up name
      setDone(TARGET_FIELDS.some((k) => k in changes) ? 'Saved. Your daily calorie and macro targets were recalculated.' : 'Saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-5">
        <div>
          <h2 className="text-lg font-bold">Profile</h2>
          <p className="mt-1 text-sm text-muted">Your height, sex, birthday and activity set your daily targets. Allergies and diet hide dishes you can't eat.</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Name" className="col-span-2">
            <Input required value={form.name} onChange={set('name')} autoComplete="name" maxLength={100} />
          </Field>

          <div className="col-span-2 flex items-baseline justify-between rounded-xl bg-bg px-3.5 py-3 text-sm">
            <span>
              <span className="font-semibold">Weight</span> <span className="text-muted">{profile.weight_lbs} lb</span>
            </span>
            <a href="#/progress" className="font-semibold text-brand">
              Log a weigh-in
            </a>
          </div>

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
            <Input required type="date" min="1900-01-01" max={latestBirthdate()} value={form.birthdate} onChange={set('birthdate')} />
          </Field>
          <Field label="How often do you exercise?">
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
            <label htmlFor="settings-allergies" className="text-[13px] font-semibold text-muted">
              Allergies
            </label>
            <div className="mt-1.5">
              <TagInput
                id="settings-allergies"
                options={ALLERGIES}
                value={form.allergies}
                onChange={(allergies) => {
                  setForm((f) => ({ ...f, allergies }))
                  setDone('')
                }}
                placeholder="Type an allergy, e.g. peanuts"
              />
            </div>
          </div>
          <div>
            <label htmlFor="settings-diet" className="text-[13px] font-semibold text-muted">
              Dietary restrictions
            </label>
            <div className="mt-1.5">
              <TagInput
                id="settings-diet"
                options={DIETARY_RESTRICTIONS}
                value={form.diet}
                onChange={(diet) => {
                  setForm((f) => ({ ...f, diet }))
                  setDone('')
                }}
                placeholder="Type a restriction, e.g. vegetarian"
              />
            </div>
          </div>
        </div>

        <ErrorNote>{error}</ErrorNote>
        {done && (
          <p role="status" className="rounded-xl bg-good/10 px-3.5 py-2.5 text-sm text-good">
            {done}
          </p>
        )}

        <Button disabled={busy || !changed} className="w-full">
          {busy ? 'Saving…' : changed ? 'Save changes' : 'No changes'}
        </Button>
      </form>
    </Card>
  )
}

function PasswordCard() {
  const empty = { current: '', next: '', confirm: '' }
  const [form, setForm] = useState(empty)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setDone(false)
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    // There is no reset by email, so a typo in the new password would lock the user out: ask for it twice
    if (form.next.length < 8) return setError('Please use a new password of at least 8 characters.')
    if (form.next !== form.confirm) return setError("The new passwords don't match.")
    if (form.next === form.current) return setError('The new password is the same as the current one.')
    setBusy(true)
    try {
      await changePassword(form.current, form.next)
      setForm(empty)
      setDone(true)
    } catch (err) {
      setError(err.status === 401 ? 'Your current password is incorrect.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="text-lg font-bold">Change password</h2>
        <Field label="Current password">
          <Input required type="password" value={form.current} onChange={set('current')} autoComplete="current-password" />
        </Field>
        <Field label="New password" hint="At least 8 characters.">
          <Input required type="password" minLength={8} maxLength={72} value={form.next} onChange={set('next')} autoComplete="new-password" />
        </Field>
        <Field label="New password again">
          <Input required type="password" value={form.confirm} onChange={set('confirm')} autoComplete="new-password" />
        </Field>
        <ErrorNote>{error}</ErrorNote>
        {done && (
          <p role="status" className="rounded-xl bg-good/10 px-3.5 py-2.5 text-sm text-good">
            Password changed. Use the new one next time you log in.
          </p>
        )}
        <Button disabled={busy} variant="dark" className="w-full">
          {busy ? 'Changing…' : 'Change password'}
        </Button>
      </form>
    </Card>
  )
}

function DeleteCard({ user, onDeleted }) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await deleteAccount(user.id, password)
      forgetUser(user.id, user.email)
      onDeleted()
    } catch (err) {
      setError(err.status === 401 ? 'Incorrect password. Your account was not deleted.' : err.message)
      setBusy(false)
    }
  }

  return (
    <Card className="ring-1 ring-bad/20">
      <h2 className="text-lg font-bold text-bad">Delete account</h2>
      <p className="mt-1 text-sm text-muted">
        Deletes your account and everything stored about it: your goal, food, weight and workout logs. This can't be undone.
      </p>
      {!open ? (
        <Button type="button" onClick={() => setOpen(true)} variant="soft" className="mt-4 w-full !bg-bad/10 !text-bad">
          Delete my account…
        </Button>
      ) : (
        <form onSubmit={submit} className="mt-4 space-y-3">
          <Field label="Enter your password to confirm">
            <Input required autoFocus type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </Field>
          <ErrorNote>{error}</ErrorNote>
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant="soft"
              onClick={() => {
                setOpen(false)
                setPassword('')
                setError('')
              }}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button disabled={busy || !password} className="!bg-bad hover:!bg-bad/90">
              {busy ? 'Deleting…' : 'Delete forever'}
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}
