import { useState } from 'react'

const FIELD = 'w-full border border-ink bg-transparent px-3 py-2.5 placeholder:text-ink-soft/70 disabled:opacity-50'

export function Bar({ label, value, max, unit = '', strong }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const over = value > max
  return (
    <div>
      <div className="flex items-baseline justify-between font-mono text-[12px] uppercase tracking-wider">
        <span className="text-ink-soft">{label}</span>
        <span className={over ? 'text-illini-deep' : 'text-ink'}>
          {Math.round(value)} / {Math.round(max)}
          {unit}
        </span>
      </div>
      <div className="mt-1.5 h-[6px] w-full bg-paper-deep">
        <div className={`h-full transition-all duration-500 ${strong ? 'bg-illini' : 'bg-ink'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function SectionHead({ n, title, sub }) {
  return (
    <div className="mb-10 grid gap-3 border-t border-ink pt-5 md:grid-cols-[120px_1fr_1fr] md:gap-8">
      <span className="font-mono text-sm text-illini-deep">{n}</span>
      <h2 className="font-serif text-4xl leading-none font-medium tracking-tight md:text-5xl">{title}</h2>
      {sub && <p className="max-w-md text-ink-soft md:justify-self-end">{sub}</p>}
    </div>
  )
}

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="font-mono text-[12px] uppercase tracking-wider text-ink-soft">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-[13px] text-ink-soft">{hint}</span>}
    </label>
  )
}

export function Input({ className = '', ...props }) {
  return <input className={`${FIELD} ${className}`} {...props} />
}

export function Select({ className = '', children, ...props }) {
  return (
    <select className={`${FIELD} ${className}`} {...props}>
      {children}
    </select>
  )
}

export function ErrorNote({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="border-l-2 border-illini-deep bg-illini/10 px-3 py-2 text-[15px] text-illini-deep">
      {children}
    </p>
  )
}

export function Loading({ children = 'Loading…' }) {
  return <p className="py-6 font-mono text-sm text-ink-soft">{children}</p>
}

export function ChoiceChips({ options, value, onChange, getLabel = (o) => o }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={`border border-ink px-4 py-2 font-mono text-[12px] uppercase tracking-wider transition-colors ${
            value === o ? 'bg-ink text-paper' : 'hover:bg-paper-deep'
          }`}
        >
          {getLabel(o)}
        </button>
      ))}
    </div>
  )
}

// Type to add from a fixed list (the backend only understands these names).
// Enter or comma adds the typed value if it matches an option, ignoring case.
export function TagInput({ id, options, value, onChange, placeholder }) {
  const [text, setText] = useState('')
  const [error, setError] = useState('')

  const query = text.trim().toLowerCase()
  const available = options.filter((o) => !value.includes(o))
  const suggestions = query ? available.filter((o) => o.toLowerCase().includes(query)) : available

  const add = (option) => {
    onChange([...value, option])
    setText('')
    setError('')
  }

  const commit = () => {
    if (!query) return
    const match = options.find((o) => o.toLowerCase() === query) || (suggestions.length === 1 ? suggestions[0] : null)
    if (!match) {
      setError(`"${text.trim()}" isn't on the list. Pick one of the suggestions below.`)
    } else if (value.includes(match)) {
      setText('')
    } else {
      add(match)
    }
  }

  return (
    <div>
      {value.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((v) => (
            <span key={v} className="flex items-center gap-1.5 bg-ink py-1 pr-1.5 pl-2.5 font-mono text-[12px] text-paper">
              {v}
              <button
                type="button"
                onClick={() => onChange(value.filter((x) => x !== v))}
                aria-label={`Remove ${v}`}
                className="px-1 text-paper/70 hover:text-illini"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        id={id}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setError('')
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            commit()
          } else if (e.key === 'Backspace' && !text && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        placeholder={placeholder}
        autoComplete="off"
        className={FIELD}
      />
      {error && <p className="mt-1 text-[13px] text-illini-deep">{error}</p>}
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => add(o)}
              className="border border-rule px-2 py-0.5 font-mono text-[12px] text-ink-soft transition-colors hover:border-ink hover:text-ink"
            >
              + {o}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
