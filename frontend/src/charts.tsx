import type { ReactNode } from 'react'
import { IconAlert, Plate } from './ui'
import { pct, pts } from './format'


const UNMAPPED = 'Other/Unmapped'

/** Shared horizontal scale: 0 … max, with an optional dashed cap line. */
function Track({ max, cap, children }: { max: number; cap?: number; children: ReactNode }) {
  return (
    <div className="relative h-5">
      <div className="absolute inset-y-0 left-0 w-px bg-ink-3" />
      {children}
      {cap !== undefined && cap < max && (
        <div
          aria-hidden
          className="absolute -inset-y-1 border-l border-dashed border-ink-2"
          style={{ left: `${(cap / max) * 100}%` }}
        />
      )}
    </div>
  )
}

const at = (v: number, max: number) => `${Math.min(100, (v / max) * 100)}%`

/**
 * The look-through dumbbell. Navy: what you hold directly. Ochre hatch: what your funds add on top.
 * The ring marks effective exposure, the number you actually carry.
 */
export function Dumbbell({
  rows,
  cap,
  unseen = [],
}: {
  rows: { symbol: string; direct: number; effective: number }[]
  cap: number
  unseen?: { label: string; weight: number }[]
}) {
  const max = Math.max(cap, ...rows.map((r) => r.effective), ...unseen.map((u) => u.weight)) * 1.12
  return (
    <div role="list" className="space-y-1.5">
      <div className="grid grid-cols-[1fr_5.5rem] items-end gap-3 text-[0.75rem] text-ink-3 sm:grid-cols-[minmax(6.5rem,11rem)_1fr_6.5rem]">
        <span className="hidden sm:block" />
        <div className="relative h-4">
          <span className="absolute left-0">0%</span>
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: at(cap, max) }}>
            {pct(cap, 0)} cap
          </span>
        </div>
        <span className="text-right">effective</span>
      </div>
      {rows.map((r, i) => {
        const breach = r.effective > cap
        const via = r.effective - r.direct
        return (
          <div
            role="listitem"
            key={r.symbol}
            className="grid grid-cols-[1fr_5.5rem] items-center gap-x-3 gap-y-0.5 sm:grid-cols-[minmax(6.5rem,11rem)_1fr_6.5rem]"
            aria-label={`${r.symbol}: direct ${pct(r.direct)}, effective ${pct(r.effective)}`}
          >
            <span className="col-span-2 truncate text-[0.9rem] sm:col-span-1">
              <Plate id={r.symbol} compact />
            </span>
            <Track max={max} cap={cap}>
              <div
                className="draw-x absolute inset-y-[6px] bg-direct"
                style={{ left: 0, width: at(r.direct, max), animationDelay: `${i * 40}ms` }}
              />
              {via > 0.0005 && (
                <div
                  className="draw-x hatch-via absolute inset-y-[3px] outline outline-1 outline-via"
                  style={{ left: at(r.direct, max), width: at(via, max), animationDelay: `${i * 40 + 200}ms` }}
                />
              )}
              {r.direct > 0 && (
                <div
                  className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-direct ring-2 ring-panel"
                  style={{ left: at(r.direct, max) }}
                />
              )}
              <div
                className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-direct bg-panel"
                style={{ left: at(r.effective, max) }}
              />
            </Track>
            <span className={`num text-right text-[0.9rem] ${breach ? 'font-semibold text-alert' : ''}`}>
              {breach && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
              {pct(r.effective)}
              {via > 0.0005 && <span className="block text-[0.75rem] text-via">{pts(via)} via funds</span>}
            </span>
          </div>
        )
      })}
      {unseen.map((u) => (
        <div
          role="listitem"
          key={u.label}
          className="grid grid-cols-[1fr_5.5rem] items-center gap-x-3 gap-y-0.5 border-t border-dashed border-rule pt-1.5 sm:grid-cols-[minmax(6.5rem,11rem)_1fr_6.5rem]"
          aria-label={`${u.label}: ${pct(u.weight)} of the portfolio, holdings not yet visible`}
        >
          <span className="col-span-2 truncate text-[0.9rem] text-ink-2 italic sm:col-span-1" title={u.label}>
            {u.label}
          </span>
          <Track max={max} cap={cap}>
            <div className="draw-x hatch-unmapped absolute inset-y-[3px] left-0" style={{ width: at(u.weight, max) }} />
          </Track>
          <span className="num text-right text-[0.9rem] text-ink-2">
            {pct(u.weight)}
            <span className="block font-sans text-[0.75rem] text-ink-3">not yet visible</span>
          </span>
        </div>
      ))}
    </div>
  )
}

/** Sector exposure: direct (navy) plus what funds add (hatched), against the sector cap. */
export function SectorBars({
  rows,
  cap,
  unmappedLabel = 'Inside funds, not yet visible',
}: {
  rows: { sector: string; direct: number; effective: number }[]
  cap: number
  unmappedLabel?: string
}) {
  const max = Math.max(cap, ...rows.map((r) => r.effective)) * 1.1
  return (
    <div className="space-y-2">
      {rows.map((r, i) => {
        const unmapped = r.sector === UNMAPPED
        const breach = !unmapped && r.effective > cap
        return (
          <div key={r.sector}>
            <div className="flex items-baseline justify-between gap-2 text-[0.85rem]">
              <span className={unmapped ? 'text-ink-2 italic' : 'text-ink'}>
                {unmapped ? unmappedLabel : r.sector}
              </span>
              <span className={`num ${breach ? 'font-semibold text-alert' : 'text-ink-2'}`}>
                {breach && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
                {pct(r.effective)}
              </span>
            </div>
            <Track max={max} cap={unmapped ? undefined : cap}>
              {unmapped ? (
                <div className="draw-x hatch-unmapped absolute inset-y-1 left-0" style={{ width: at(r.effective, max) }} />
              ) : (
                <>
                  <div
                    className="draw-x absolute inset-y-1 left-0 bg-direct"
                    style={{ width: at(r.direct, max), animationDelay: `${i * 40}ms` }}
                  />
                  {r.effective - r.direct > 0.0005 && (
                    <div
                      className="draw-x hatch-via absolute inset-y-0.5 outline outline-1 outline-via"
                      style={{ left: at(r.direct, max), width: at(r.effective - r.direct, max), animationDelay: `${i * 40 + 200}ms` }}
                    />
                  )}
                </>
              )}
            </Track>
          </div>
        )
      })}
    </div>
  )
}

/** Diverging bar around zero. Direction carries the sign; colour only separates the two halves. */
export function SignedBar({ value, max, label }: { value: number; max: number; label: string }) {
  const w = `${Math.min(50, (Math.abs(value) / (max || 1)) * 50)}%`
  return (
    <div className="relative h-3 w-full min-w-16" role="img" aria-label={label}>
      <div className="absolute inset-y-0 left-1/2 w-px bg-ink-3" />
      <div
        className={`absolute inset-y-0.5 ${value >= 0 ? 'left-1/2 bg-direct' : 'right-1/2 bg-ink-2'}`}
        style={{ width: w }}
      />
    </div>
  )
}

/** 0–100 score as a filled rule with its number. */
export function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-ink-3">n/a</span>
  return (
    <span className="inline-flex w-full items-center gap-2">
      <span className="relative h-1.5 flex-1 bg-rule-soft">
        <span className="absolute inset-y-0 left-0 bg-direct" style={{ width: `${value}%` }} />
      </span>
      <span className="num w-8 text-right text-[0.85rem]">{Math.round(value)}</span>
    </span>
  )
}

/** Where the money sits: one 100% strip, a segment per holding, labelled with its share. */
export function WeightStrip({ rows }: { rows: { id: string; label: string; kind: 'STOCK' | 'MF' | 'CASH'; weight: number }[] }) {
  const fill = { STOCK: 'bg-direct', MF: 'hatch-via', CASH: 'bg-rule' } as const
  const sorted = [...rows].sort((a, b) => b.weight - a.weight)
  return (
    <div>
      <div className="flex h-7 w-full overflow-hidden" role="img" aria-label={sorted.map((r) => `${r.label} ${pct(r.weight)}`).join(', ')}>
        {sorted.map((r, i) => (
          <div
            key={r.id}
            className={`draw-x h-full border-r-2 border-panel last:border-r-0 ${fill[r.kind]}`}
            style={{ width: `${r.weight * 100}%`, animationDelay: `${i * 50}ms` }}
          />
        ))}
      </div>
      <div className="mt-1.5 flex w-full text-[0.8rem]">
        {sorted.map((r) => (
          <div key={r.id} className="min-w-0 truncate pr-2" style={{ width: `${r.weight * 100}%` }} title={`${r.label} ${pct(r.weight)}`}>
            {r.weight >= 0.06 && (
              <>
                <span className="block truncate font-semibold text-ink">{r.label}</span>
                <span className="num text-ink-2">{pct(r.weight)}</span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/** Daily returns as a histogram; the days beyond VaR are the shaded tail, annotated on the chart.
 *  Bars are SVG stretched to the width; all text is HTML so it stays readable at phone width. */
export function TailHistogram({
  edges,
  counts,
  varLoss,
  odds,
}: {
  edges: number[]
  counts: number[]
  varLoss: number
  odds: number
}) {
  const lo = edges[0], hi = edges[edges.length - 1]
  const xp = (v: number) => ((v - lo) / (hi - lo)) * 100
  const top = Math.max(...counts, 1)
  const cut = -varLoss
  const inTail = (i: number) => edges[i + 1] <= cut + 1e-12
  const tailDays = counts.reduce((a, c, i) => a + (inTail(i) ? c : 0), 0)
  const left = xp(cut)
  return (
    <figure role="img" aria-label={`Daily returns; ${tailDays} days fell below ${pct(cut)}`}>
      <div className="relative mb-1 h-10">
        <div
          className={`absolute bottom-0 text-[0.8rem] leading-tight ${left < 50 ? 'pl-2 text-left' : 'pr-2 text-right'}`}
          style={left < 50 ? { left: `${left}%` } : { right: `${100 - left}%` }}
        >
          <span className="block font-bold text-ink">1-in-{odds} bad day: {pct(cut)}</span>
          <span className="text-ink-2">{tailDays} days fell further</span>
        </div>
      </div>
      <div className="relative h-32">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
          <defs>
            <pattern id="tail" width="1.6" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="1.6" height="3" fill="#f8e3e1" />
              <rect width="0.6" height="3" fill="#b3261e" />
            </pattern>
          </defs>
          {counts.map((c, i) => (
            <rect
              key={i}
              x={xp(edges[i]) + 0.15}
              y={100 - (c / top) * 100}
              width={Math.max(0, xp(edges[i + 1]) - xp(edges[i]) - 0.3)}
              height={(c / top) * 100}
              fill={inTail(i) ? 'url(#tail)' : '#1f4e79'}
            />
          ))}
        </svg>
        <div className="absolute -top-2 bottom-0 border-l border-dashed border-ink" style={{ left: `${left}%` }} />
      </div>
      <div className="num relative h-5 border-t border-ink-3 text-[0.75rem] text-ink-3">
        <span className="absolute left-0 pt-0.5">{pct(lo)}</span>
        {lo < 0 && hi > 0 && <span className="absolute -translate-x-1/2 pt-0.5" style={{ left: `${xp(0)}%` }}>{pct(0)}</span>}
        <span className="absolute right-0 pt-0.5">{pct(hi)}</span>
      </div>
    </figure>
  )
}
