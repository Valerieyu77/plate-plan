import { useEffect, useState } from 'react'
import { getGoal, getMe, onUnauthorized, onWaking } from './api'
import { Button, Card, Loading } from './components/ui'
import AuthPage from './pages/AuthPage'
import GoalPage from './pages/GoalPage'
import PlanPage from './pages/PlanPage'
import ProgressPage from './pages/ProgressPage'
import { clearToken, getToken, setLastEmail, setToken } from './session'

// Tiny hash router: #/ (sign up / log in), #/goal, #/plan, #/progress
const currentRoute = () => window.location.hash.replace(/^#/, '') || '/'
const navigate = (path) => {
  window.location.hash = path
}

function useRoute() {
  const [route, setRoute] = useState(currentRoute)
  useEffect(() => {
    const onChange = () => {
      setRoute(currentRoute())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

// Bottom tab bar: [path, label, icon path data (24x24, stroked)]
const TABS = [
  ['/plan', 'Plan', 'M4 6h16M4 12h16M4 18h10'],
  ['/progress', 'Progress', 'M12 3a9 9 0 1 0 9 9M12 3v9h9'],
  ['/goal', 'Goal', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-4a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z'],
]

export default function App() {
  const route = useRoute()
  const [user, setUser] = useState(null)
  const [restoring, setRestoring] = useState(() => getToken() !== null)
  const [restoreError, setRestoreError] = useState('')
  const [waking, setWaking] = useState(false)

  useEffect(() => onWaking(setWaking), [])

  // Reload the signed-in user from the token saved in localStorage. If the server can't be reached,
  // keep the token and offer "Try again" rather than showing the log-in page. A rejected token
  // (expired, or the account is gone) is handled by onUnauthorized below.
  const loadUser = () =>
    getMe()
      .then(setUser)
      .catch((err) => {
        if (err.status !== 401) setRestoreError(err.message)
      })
      .finally(() => setRestoring(false))

  useEffect(() => {
    if (getToken() !== null) loadUser()
  }, [])

  const retryRestore = () => {
    setRestoring(true)
    setRestoreError('')
    loadUser()
  }

  const signedIn = async ({ token, user: u }, { isNew }) => {
    setToken(token)
    setLastEmail(u.email)
    setUser(u)
    setRestoreError('')
    if (isNew) return navigate('/goal')
    try {
      await getGoal(u.id)
      navigate('/plan')
    } catch {
      navigate('/goal')
    }
  }

  const logOut = () => {
    clearToken()
    setRestoreError('')
    setUser(null)
    navigate('/')
  }

  // The server rejected the saved token: back to the log-in page
  useEffect(() => onUnauthorized(logOut), [])

  let page
  if (restoring) page = <Loading />
  else if (!user && restoreError)
    page = (
      <Card className="mt-6 text-center">
        <p className="font-semibold">Couldn't load your account</p>
        <p className="mt-1 text-sm text-muted">{restoreError}</p>
        <Button onClick={retryRestore} className="mt-4 w-full">
          Try again
        </Button>
        <button onClick={logOut} className="mt-3 text-sm font-medium text-muted hover:text-ink">
          Use a different account
        </button>
      </Card>
    )
  else if (!user || route === '/') page = <AuthPage onSignedIn={signedIn} />
  else if (route === '/goal') page = <GoalPage user={user} onContinue={() => navigate('/plan')} />
  else if (route === '/progress') page = <ProgressPage user={user} onSetGoal={() => navigate('/goal')} />
  else page = <PlanPage user={user} onSetGoal={() => navigate('/goal')} />

  const inApp = user && !restoring && route !== '/'

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 border-b border-line/70 bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-xl items-center justify-between px-4">
          <a href={user ? '#/plan' : '#/'} className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-base font-bold text-white">P</span>
            <span className="text-[17px] font-bold tracking-tight">Plate Plan</span>
          </a>
          {inApp && (
            <div className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-ink text-sm font-semibold text-white" title={user.name}>
                {user.name.trim().charAt(0).toUpperCase()}
              </span>
              <button onClick={logOut} className="rounded-lg px-2 py-1.5 text-sm font-medium text-muted transition-colors hover:text-ink">
                Log out
              </button>
            </div>
          )}
        </div>
        {waking && (
          <p role="status" className="flex items-center justify-center gap-2 bg-brand-soft px-4 py-2 text-[13px] font-medium text-brand-deep">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand/30 border-t-brand" aria-hidden="true" />
            Server is waking up, please wait…
          </p>
        )}
      </header>

      <main className={`mx-auto max-w-xl px-4 pt-5 ${inApp ? 'pb-[calc(6rem+env(safe-area-inset-bottom))]' : 'pb-12'}`}>
        {page}
      </main>

      {inApp && (
        <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md">
          <div className="mx-auto grid max-w-xl grid-cols-3">
            {TABS.map(([path, label, icon]) => {
              // Any unknown route shows the Plan page, so highlight Plan for it too
              const active = route === path || (path === '/plan' && !TABS.some(([p]) => p === route))
              return (
                <a
                  key={path}
                  href={`#${path}`}
                  aria-current={active ? 'page' : undefined}
                  className={`flex flex-col items-center gap-1 pt-2.5 pb-2 text-[11px] font-semibold transition-colors ${active ? 'text-brand' : 'text-muted hover:text-ink'}`}
                >
                  <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d={icon} />
                  </svg>
                  {label}
                </a>
              )
            })}
          </div>
        </nav>
      )}
    </div>
  )
}
