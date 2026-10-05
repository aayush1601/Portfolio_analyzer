import { useContext, useMemo, useState, type ReactNode } from 'react'
import type { Loadable } from './api'
import { pct } from './format'
import { reorder, slug } from './motion'
import { PlateContext } from './plates'

// ---------- icons (authored, 16px grid, 1.5 stroke) ----------
type IconProps = { className?: string; title?: string }
const Svg = ({ children, className = 'size-4', title }: IconProps & { children: ReactNode }) => (
  <svg viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth={1.5}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
    {title && <title>{title}</title>}
    {children}
  </svg>
)
export const IconUp = (p: IconProps) => <Svg {...p}><path d="M8 3.5 13 11H3z" fill="currentColor" stroke="none" /></Svg>
export const IconDown = (p: IconProps) => <Svg {...p}><path d="M8 12.5 3 5h10z" fill="currentColor" stroke="none" /></Svg>
export const IconAlert = (p: IconProps) => <Svg {...p}><path d="M8 2.2 14.5 13.5h-13z" /><path d="M8 6.5v3.2M8 11.6v.1" /></Svg>
export const IconExternal = (p: IconProps) => (
  <Svg {...p}><path d="M9.5 2.5h4v4M13.5 2.5 7.5 8.5M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3" /></Svg>
)
export const IconPlus = (p: IconProps) => <Svg {...p}><path d="M8 3v10M3 8h10" /></Svg>
export const IconTrash = (p: IconProps) => <Svg {...p}><path d="M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.7 8.5h6.6l.7-8.5" /></Svg>
export const IconRefresh = (p: IconProps) => <Svg {...p}><path d="M13 8a5 5 0 1 1-1.5-3.6M13 2.5v2.8h-2.8" /></Svg>
export const IconArrow = (p: IconProps) => <Svg {...p}><path d="M3 8h10M9 4l4 4-4 4" /></Svg>

/** The app mark: a rounded green tile with a lens, i.e. looking through. */
export function Mark({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--color-brand)" />
      <circle cx="14.5" cy="14.5" r="6.5" fill="none" stroke="#fff" strokeWidth="2.6" />
      <path d="M19.3 19.3 24 24" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M11.5 16.5 14 13.5l2 2 2.5-3" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** Signed figure: sign, arrow and colour together, so it never relies on colour alone. */
export function Delta({ value, children, className = '' }: { value: number; children: ReactNode; className?: string }) {
  const Icon = value > 0 ? IconUp : value < 0 ? IconDown : null
  const tone = value > 0 ? 'text-brand-ink' : value < 0 ? 'text-loss' : 'text-ink-2'
  return (
    <span className={`num inline-flex items-center gap-1 whitespace-nowrap ${tone} ${className}`}>
      {Icon && <Icon className="size-2.5" title={value > 0 ? 'up' : 'down'} />}
      {children}
    </span>
  )
}

// ---------- company identity ----------
const AVATAR_TONES = [
  'bg-accent-soft text-accent-ink',
  'bg-brand-soft text-brand-ink',
  'bg-via-soft text-via-ink',
  'bg-line-soft text-ink-2',
]
function avatarTone(id: string) {
  let h = 0
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return AVATAR_TONES[h % AVATAR_TONES.length]
}

/** Monogram tile standing in for a logo; stable colour per company. */
export function Avatar({ id, label, size = 'md' }: { id: string; label?: string; size?: 'sm' | 'md' }) {
  const words = (label ?? id).replace(/[^A-Za-z0-9 ]/g, ' ').trim().split(/\s+/)
  const text = (words.length > 1 ? words.slice(0, 2).map((w) => w[0]).join('') : words[0].slice(0, 2)).toUpperCase()
  const dim = size === 'sm' ? 'size-6 text-[0.6rem] rounded-md' : 'size-10 text-[0.8rem] rounded-xl'
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center font-extrabold ${dim} ${avatarTone(id)}`}>
      {text || '·'}
    </span>
  )
}

/** symbol · sector · effective %: the same plate wherever a company appears. */
export function Plate({ id, compact = false }: { id: string; compact?: boolean }) {
  const info = useContext(PlateContext)[id] ?? {}
  const isFund = /^\d+$/.test(id)
  return (
    <span className="inline-flex min-w-0 items-baseline gap-1.5" title={info.name}>
      <span className="truncate font-bold text-ink">{isFund ? info.name ?? id : id}</span>
      {!compact && info.sector && <span className="truncate text-[0.85em] text-ink-3">{info.sector}</span>}
      {info.effective !== undefined && <span className="num shrink-0 text-[0.85em] text-ink-2">{pct(info.effective)}</span>}
    </span>
  )
}

// ---------- layout ----------
export function Card(props: {
  title?: ReactNode
  dek?: ReactNode
  source?: ReactNode
  aside?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-[var(--radius-card)] border border-line bg-panel shadow-[var(--shadow-card)] ${props.className ?? ''}`}>
      {(props.title || props.aside) && (
        <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-5 pt-5 sm:px-6">
          <div className="max-w-[72ch] flex-1 basis-[28rem]">
            {props.title && <h2 className="headline text-[1.08rem] leading-snug font-bold text-ink sm:text-[1.15rem]">{props.title}</h2>}
            {props.dek && <p className="mt-1 text-[0.9rem] text-ink-2">{props.dek}</p>}
          </div>
          {props.aside}
        </header>
      )}
      <div className="px-5 pt-4 pb-5 sm:px-6">{props.children}</div>
      {props.source && (
        <footer className="border-t border-line-soft px-5 py-3 text-[0.78rem] text-ink-3 sm:px-6">{props.source}</footer>
      )}
    </section>
  )
}

/** Backend notes in the reader's language: fund names instead of scheme codes, no file paths. */
export function Notes({ notes }: { notes: string[] }) {
  const plates = useContext(PlateContext)
  if (!notes.length) return null
  const human = (n: string) =>
    n
      .replace(/fund (\d{5,6})/g, (_, code) => plates[code]?.name ?? `fund ${code}`)
      .replace(/counts as Other\/Unmapped/g, 'is shown as not yet visible')
      .replace(/ in config\/[\w./]+/g, ' yet')
      .replace(/ \(see docs\/[\w./]+\)/g, ' (see the model card)')
      .replace(/run app\.services\.ml/g, 'the model has not been trained yet')
      .replace(/^expected_return is shown for information only \(weight 0\): the Phase 9 model/, 'Expected return is shown for information only and carries no weight: the return model')
      .replace(/^expected_return needs the Phase 9 model: /, 'Expected return needs the return model: ')
  return (
    <ul className="space-y-1">
      {notes.map((n) => (
        <li key={n} className="flex gap-2">
          <span aria-hidden className="mt-[0.55em] size-1 shrink-0 rounded-full bg-ink-3" />
          {human(n)}
        </li>
      ))}
    </ul>
  )
}

export function Legend({ items }: { items: { swatch: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[0.82rem] text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span aria-hidden className={`inline-block h-2.5 w-4 rounded-sm ${i.swatch}`} />
          {i.label}
        </span>
      ))}
    </div>
  )
}

export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'quiet' }) {
  const { variant = 'quiet', className = '', ...rest } = props
  const look =
    variant === 'primary'
      ? 'bg-brand-ink text-white hover:bg-brand-deep disabled:bg-ink-3'
      : 'border border-line bg-panel text-ink hover:border-ink-3 disabled:text-ink-3'
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-[0.88rem] font-bold transition-colors disabled:cursor-not-allowed ${look} ${className}`}
    />
  )
}

/** Pill segmented control (time ranges, list modes). */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-full bg-line-soft p-1">
      {options.map((o) => {
        const on = o.value === value
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            className={`rounded-full px-3 py-1 text-[0.82rem] font-bold whitespace-nowrap transition-colors ${
              on ? 'bg-panel text-ink shadow-[0_1px_3px_rgb(30_34_53/0.12)]' : 'text-ink-2 hover:text-ink'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

type Tone = 'neutral' | 'gain' | 'loss' | 'accent' | 'via'
const CHIP: Record<Tone, string> = {
  neutral: 'bg-line-soft text-ink-2',
  gain: 'bg-brand-soft text-brand-ink',
  loss: 'bg-loss-soft text-loss',
  accent: 'bg-accent-soft text-accent-ink',
  via: 'bg-via-soft text-via-ink',
}
export function Chip({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[0.78rem] font-bold whitespace-nowrap ${CHIP[tone]}`}>
      {children}
    </span>
  )
}

/** Loading / error states for one request; stale data dims while a refetch is in flight. */
export function Status<T>({ q, what, children }: { q: Loadable<T>; what: string; children: (d: T) => ReactNode }) {
  if (q.error)
    return (
      <div role="alert" className="rounded-[var(--radius-card)] border border-loss/30 bg-loss-soft px-6 py-5">
        <p className="font-bold text-ink">Couldn’t load {what}.</p>
        <p className="mt-1 text-ink-2">{q.error}</p>
        <Button className="mt-3" onClick={q.reload}>
          <IconRefresh /> Try again
        </Button>
      </div>
    )
  if (!q.data)
    return (
      <div className="rounded-[var(--radius-card)] border border-line bg-panel px-6 py-10 text-ink-3" aria-busy="true">
        Loading {what}…
      </div>
    )
  return (
    <div className={`min-w-0 ${q.loading ? 'refetching' : 'settled'}`} aria-busy={q.loading}>
      {children(q.data)}
    </div>
  )
}

// ---------- sortable table ----------
export type Column<T> = {
  key: string
  label: ReactNode
  render: (row: T) => ReactNode
  sort?: (row: T) => number | string
  align?: 'left' | 'right'
  className?: string
}

export function Table<T>({
  rows,
  columns,
  rowKey,
  initialSort,
  caption,
}: {
  rows: T[]
  columns: Column<T>[]
  rowKey: (r: T) => string
  initialSort?: { key: string; dir: 'asc' | 'desc' }
  caption: string
}) {
  const [sort, setSort] = useState(initialSort)
  const vtPrefix = `row-${slug(caption)}`
  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sort?.key)
    if (!col?.sort || !sort) return rows
    const f = col.sort
    return [...rows].sort((a, b) => {
      const x = f(a), y = f(b)
      const c = x < y ? -1 : x > y ? 1 : 0
      return sort.dir === 'asc' ? c : -c
    })
  }, [rows, columns, sort])
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[640px] border-collapse text-[0.9rem]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-left text-[0.78rem] text-ink-3">
            {columns.map((c) => {
              const active = sort?.key === c.key
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`px-3 py-2.5 font-bold first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6 ${c.align === 'right' ? 'text-right' : ''}`}
                >
                  {c.sort ? (
                    <button
                      className={`inline-flex items-center gap-1 hover:text-ink ${active ? 'text-ink' : ''}`}
                      onClick={() => reorder(() => setSort({ key: c.key, dir: active && sort!.dir === 'desc' ? 'asc' : 'desc' }))}
                    >
                      {c.label}
                      <span aria-hidden className={active ? '' : 'opacity-0'}>
                        {sort?.dir === 'asc' ? <IconUp className="size-2" /> : <IconDown className="size-2" />}
                      </span>
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={rowKey(r)}
              className="border-b border-line-soft align-middle last:border-b-0 hover:bg-canvas/70"
              style={{ viewTransitionName: `${vtPrefix}-${slug(rowKey(r))}` }}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`px-3 py-3 first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6 ${c.align === 'right' ? 'text-right' : ''} ${c.className ?? ''}`}
                >
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
