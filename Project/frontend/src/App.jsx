import { useEffect, useState } from 'react'
import { getGoal, getUser } from './api'
import { ErrorNote, Loading } from './components/ui'
import AuthPage from './pages/AuthPage'
import GoalPage from './pages/GoalPage'
import PlanPage from './pages/PlanPage'
import ProgressPage from './pages/ProgressPage'
import { clearUserId, getUserId, rememberAccount, setUserId } from './session'

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

const NAV = [
  ['/goal', 'Goal'],
  ['/plan', 'Plan a meal'],
  ['/progress', 'Progress'],
]

export default function App() {
  const route = useRoute()
  const [user, setUser] = useState(null)
  const [restoring, setRestoring] = useState(() => getUserId() !== null)
  const [restoreError, setRestoreError] = useState('')

  // Reload the signed-in user from the id saved in localStorage
  useEffect(() => {
    const id = getUserId()
    if (id === null) return
    getUser(id)
      .then((u) => {
        setUser(u)
        rememberAccount(u)
      })
      .catch((err) => {
        if (err.status === 404) clearUserId()
        else setRestoreError(err.message)
      })
      .finally(() => setRestoring(false))
  }, [])

  const signedIn = async (u, { isNew }) => {
    setUserId(u.id)
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
    clearUserId()
    setUser(null)
    navigate('/')
  }

  let page
  if (restoring) page = <Loading />
  else if (!user || route === '/') page = <AuthPage onSignedIn={signedIn} />
  else if (route === '/goal') page = <GoalPage user={user} onContinue={() => navigate('/plan')} />
  else if (route === '/progress') page = <ProgressPage user={user} onSetGoal={() => navigate('/goal')} />
  else page = <PlanPage user={user} onSetGoal={() => navigate('/goal')} />

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 md:px-10">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-rule py-6">
          <a href={user ? '#/plan' : '#/'} className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center bg-illini font-serif text-lg font-semibold text-white">I</span>
            <span className="font-serif text-xl font-medium tracking-tight">Plate Plan</span>
          </a>
          {user && (
            <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[12px] uppercase tracking-wider">
              {NAV.map(([path, label]) => (
                <a
                  key={path}
                  href={`#${path}`}
                  aria-current={route === path ? 'page' : undefined}
                  className={`transition-colors hover:text-illini-deep ${route === path ? 'text-illini-deep' : 'text-ink-soft'}`}
                >
                  {label}
                </a>
              ))}
              <span className="text-ink">{user.name}</span>
              <button onClick={logOut} className="uppercase text-ink-soft transition-colors hover:text-illini-deep">
                Log out
              </button>
            </nav>
          )}
        </header>

        {restoreError && (
          <div className="pt-6">
            <ErrorNote>{restoreError}</ErrorNote>
          </div>
        )}

        <main>{page}</main>

        <footer className="flex flex-col justify-between gap-2 border-t border-ink py-8 font-mono text-[12px] uppercase tracking-wider text-ink-soft md:flex-row">
          <span>Plate Plan · Built for the University of Illinois Urbana-Champaign</span>
          <span>Menus from UIUC Dining</span>
        </footer>
      </div>
    </div>
  )
}
