import { useContext, useMemo, useState, type ReactNode } from 'react'
import type { Loadable } from './api'
import { pct } from './format'
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
export const IconAlert = (p: IconProps) => (
  <Svg {...p}><path d="M8 2.2 14.5 13.5h-13z" /><path d="M8 6.5v3.2M8 11.6v.1" /></Svg>
)
export const IconExternal = (p: IconProps) => (
  <Svg {...p}><path d="M9.5 2.5h4v4M13.5 2.5 7.5 8.5M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3" /></Svg>
)
export const IconPlus = (p: IconProps) => <Svg {...p}><path d="M8 3v10M3 8h10" /></Svg>
export const IconTrash = (p: IconProps) => (
  <Svg {...p}><path d="M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.7 8.5h6.6l.7-8.5" /></Svg>
)
export const IconRefresh = (p: IconProps) => (
  <Svg {...p}><path d="M13 8a5 5 0 1 1-1.5-3.6M13 2.5v2.8h-2.8" /></Svg>
)

/** Signed figure with a drawn direction mark, so gains and losses never rely on colour alone. */
export function Delta({ value, children }: { value: number; children: ReactNode }) {
  const Icon = value > 0 ? IconUp : value < 0 ? IconDown : null
  return (
    <span className="num inline-flex items-center gap-1 whitespace-nowrap">
      {Icon && <Icon className="size-2.5 text-ink-2" title={value > 0 ? 'up' : 'down'} />}
      {children}
    </span>
  )
}

// ---------- the one name plate per company ----------
/** symbol · sector · effective %: identical wherever a company appears. */
export function Plate({ id, compact = false }: { id: string; compact?: boolean }) {
  const info = useContext(PlateContext)[id] ?? {}
  const isFund = /^\d+$/.test(id)
  return (
    <span className="inline-flex min-w-0 items-baseline gap-1.5 whitespace-nowrap" title={info.name}>
      <span className="font-semibold text-ink">{isFund ? info.name ?? id : id}</span>
      {!compact && info.sector && <span className="truncate text-ink-3">· {info.sector}</span>}
      {info.effective !== undefined && <span className="num text-[0.85em] text-ink-2">· {pct(info.effective)}</span>}
    </span>
  )
}

// ---------- layout ----------
export function Figure(props: {
  title: ReactNode
  dek?: ReactNode
  source?: ReactNode
  children: ReactNode
  aside?: ReactNode
  className?: string
}) {
  return (
    <section className={`border-t-2 border-ink bg-panel ${props.className ?? ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-5 pt-4 sm:px-6">
        <div className="max-w-[60ch]">
          <h2 className="headline text-xl leading-snug font-bold tracking-[-0.01em] text-ink sm:text-[1.4rem]">
            {props.title}
          </h2>
          {props.dek && <p className="mt-1 text-ink-2">{props.dek}</p>}
        </div>
        {props.aside}
      </div>
      <div className="px-5 pt-4 pb-4 sm:px-6">{props.children}</div>
      {props.source && <p className="border-t border-rule-soft px-5 py-2 text-[0.8rem] text-ink-3 sm:px-6">{props.source}</p>}
    </section>
  )
}

export function Notes({ notes }: { notes: string[] }) {
  if (!notes.length) return null
  return (
    <ul className="space-y-1 text-[0.85rem] text-ink-2">
      {notes.map((n) => (
        <li key={n} className="flex gap-2">
          <span aria-hidden className="mt-[0.55em] size-1 shrink-0 rounded-full bg-ink-3" />
          {n}
        </li>
      ))}
    </ul>
  )
}

export function Legend({ items }: { items: { swatch: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[0.85rem] text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span aria-hidden className={`inline-block h-2.5 w-4 ${i.swatch}`} />
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
      ? 'bg-bar text-bar-ink hover:bg-direct disabled:bg-ink-3'
      : 'border border-rule bg-panel text-ink hover:border-ink-3 disabled:text-ink-3'
  return (
    <button
      {...rest}
      className={`inline-flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${look} ${className}`}
    />
  )
}

/** Loading / error states for one request, with the page's own copy. */
export function Status<T>({ q, what, children }: { q: Loadable<T>; what: string; children: (d: T) => ReactNode }) {
  if (q.error)
    return (
      <div role="alert" className="border-t-2 border-alert bg-panel px-6 py-5">
        <p className="font-semibold text-ink">Couldn’t load {what}.</p>
        <p className="mt-1 text-ink-2">{q.error}</p>
        <Button className="mt-3" onClick={q.reload}>
          <IconRefresh /> Try again
        </Button>
      </div>
    )
  if (!q.data)
    return (
      <div className="border-t-2 border-rule bg-panel px-6 py-10 text-ink-3" aria-busy="true">
        <span>Loading {what}…</span>
      </div>
    )
  return <>{children(q.data)}</>
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
  rowClass,
  caption,
}: {
  rows: T[]
  columns: Column<T>[]
  rowKey: (r: T) => string
  initialSort?: { key: string; dir: 'asc' | 'desc' }
  rowClass?: (r: T) => string
  caption: string
}) {
  const [sort, setSort] = useState(initialSort)
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
          <tr className="border-b border-ink text-left text-[0.8rem] text-ink-2">
            {columns.map((c) => {
              const active = sort?.key === c.key
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`px-3 py-2 font-semibold first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6 ${c.align === 'right' ? 'text-right' : ''}`}
                >
                  {c.sort ? (
                    <button
                      className={`inline-flex items-center gap-1 hover:text-ink ${active ? 'text-ink' : ''}`}
                      onClick={() =>
                        setSort({ key: c.key, dir: active && sort!.dir === 'desc' ? 'asc' : 'desc' })
                      }
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
            <tr key={rowKey(r)} className={`border-b border-rule-soft align-top hover:bg-ground/60 ${rowClass?.(r) ?? ''}`}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`px-3 py-2 first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6 ${c.align === 'right' ? 'text-right' : ''} ${c.className ?? ''}`}
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
