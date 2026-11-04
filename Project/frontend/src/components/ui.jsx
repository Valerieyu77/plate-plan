import { useState } from 'react'

const FIELD =
  'w-full rounded-xl border border-line bg-surface px-3.5 py-3 text-[15px] placeholder:text-muted/70 transition-colors focus:border-brand focus:outline-none focus-visible:outline-none focus:ring-2 focus:ring-brand/20 disabled:opacity-50'

const BUTTON = {
  primary: 'bg-brand text-white hover:bg-brand-deep',
  dark: 'bg-ink text-white hover:bg-ink/90',
  soft: 'bg-brand-soft text-brand-deep hover:bg-brand-soft/70',
}

const buttonClass = (variant, className) =>
  `rounded-xl px-5 py-3.5 text-[15px] font-semibold transition-colors disabled:opacity-60 ${BUTTON[variant]} ${className}`

export function Button({ variant = 'primary', className = '', ...props }) {
  return <button className={buttonClass(variant, className)} {...props} />
}

// A link that looks like a Button, for moving to another page
export function ButtonLink({ variant = 'primary', className = '', ...props }) {
  return <a className={`inline-block text-center ${buttonClass(variant, className)}`} {...props} />
}

export function Card({ tone = 'bg-surface', className = '', children }) {
  return <div className={`rounded-2xl ${tone} p-5 shadow-[0_1px_3px_rgba(19,41,75,0.06)] ${className}`}>{children}</div>
}

export function PageHeader({ title, sub, action }) {
  return (
    <div className="mb-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {action}
      </div>
      {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  )
}

export function Label({ children, className = '' }) {
  return <p className={`text-[13px] font-semibold text-muted ${className}`}>{children}</p>
}

// Small date picker that looks like a chip, for page headers
export function DateChip({ value, onChange, max }) {
  return (
    <input
      type="date"
      value={value}
      max={max}
      onChange={(e) => e.target.value && onChange(e.target.value)}
      aria-label="Date"
      className="shrink-0 rounded-full border border-line bg-surface px-3 py-1.5 text-sm font-medium focus:border-brand focus:outline-none"
    />
  )
}

// Thin bar for one nutrient: value out of max, red once it's over
export function Bar({ label, value, max, unit = '', color = 'bg-ink' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const over = value > max
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className={over ? 'font-medium text-bad' : 'text-muted'}>
          {Math.round(value)} / {Math.round(max)}
          {unit}
        </span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-bg">
        <div className={`h-full rounded-full transition-all duration-500 ${over ? 'bg-bad' : color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// Circular progress: value out of max, with whatever is passed as children in the middle
export function ProgressRing({ value, max, size = 180, stroke = 14, label, children }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = max > 0 ? Math.min(1, value / max) : 0
  const over = value > max
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" role="img" aria-label={label}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-bg)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={over ? 'var(--color-bad)' : 'var(--color-brand)'}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-[13px] font-semibold text-muted">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-[13px] text-muted">{hint}</span>}
    </label>
  )
}

export function Input({ className = '', ...props }) {
  return <input className={`${FIELD} ${className}`} {...props} />
}

export function Select({ className = '', children, ...props }) {
  return (
    <div className="relative">
      <select className={`${FIELD} appearance-none pr-10 ${className}`} {...props}>
        {children}
      </select>
      <svg viewBox="0 0 24 24" className="pointer-events-none absolute top-1/2 right-3.5 h-4 w-4 -translate-y-1/2 text-muted" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m6 9 6 6 6-6" />
      </svg>
    </div>
  )
}

export function ErrorNote({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="rounded-xl bg-bad/10 px-3.5 py-2.5 text-sm text-bad">
      {children}
    </p>
  )
}

export function Loading({ children = 'Loading…' }) {
  return (
    <p className="flex items-center gap-2 py-6 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand" />
      {children}
    </p>
  )
}

// One row of pill buttons that scrolls sideways on small screens.
// The row bleeds to the screen edges (-mx-4 px-4) so chips don't get cut off at the gutter.
export function ChipScroller({ options, value, onChange, getLabel = (o) => o, label }) {
  return (
    <div role="group" aria-label={label} className="no-scrollbar -mx-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={`shrink-0 snap-start rounded-full px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
            value === o ? 'bg-ink text-white' : 'bg-surface text-ink ring-1 ring-line hover:ring-ink/30'
          }`}
        >
          {getLabel(o)}
        </button>
      ))}
    </div>
  )
}

// Two or three options side by side, like an iOS segmented control
export function Segmented({ options, value, onChange }) {
  return (
    <div className="grid rounded-xl bg-bg p-1" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }} role="tablist">
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={value === key}
          onClick={() => onChange(key)}
          className={`rounded-lg py-2 text-sm font-semibold transition-colors ${value === key ? 'bg-surface shadow-sm' : 'text-muted'}`}
        >
          {label}
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
            <span key={v} className="flex items-center gap-1 rounded-full bg-ink py-1 pr-1 pl-3 text-[13px] font-medium text-white">
              {v}
              <button
                type="button"
                onClick={() => onChange(value.filter((x) => x !== v))}
                aria-label={`Remove ${v}`}
                className="grid h-5 w-5 place-items-center rounded-full text-white/70 hover:bg-white/15 hover:text-white"
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
      {error && <p className="mt-1 text-[13px] text-bad">{error}</p>}
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => add(o)}
              className="rounded-full bg-bg px-3 py-1 text-[13px] text-muted transition-colors hover:bg-line hover:text-ink"
            >
              + {o}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
