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
  const fill = { STOCK: 'bg-direct', MF: 'bg-[#8fa9c4]', CASH: 'bg-rule' } as const
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

/** Daily returns as a histogram; the days beyond VaR are the shaded tail, annotated on the chart. */
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
  const W = 640, H = 170, pad = { l: 8, r: 8, t: 34, b: 26 }
  const lo = edges[0], hi = edges[edges.length - 1]
  const x = (v: number) => pad.l + ((v - lo) / (hi - lo)) * (W - pad.l - pad.r)
  const top = Math.max(...counts, 1)
  const y = (c: number) => H - pad.b - (c / top) * (H - pad.t - pad.b)
  const cut = -varLoss
  const tailDays = counts.reduce((a, c, i) => a + (edges[i + 1] <= cut + 1e-12 ? c : 0), 0)
  const ticks = [lo, 0, hi].filter((v, i, a) => a.indexOf(v) === i)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`Daily returns; ${tailDays} days fell below ${pct(cut)}`}>
      <defs>
        <pattern id="tail" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="5" fill="#f8e3e1" />
          <rect width="2" height="5" fill="#b3261e" />
        </pattern>
      </defs>
      {counts.map((c, i) => {
        const inTail = edges[i + 1] <= cut + 1e-12
        return (
          <rect
            key={i}
            x={x(edges[i]) + 0.5}
            y={y(c)}
            width={Math.max(0, x(edges[i + 1]) - x(edges[i]) - 1)}
            height={H - pad.b - y(c)}
            fill={inTail ? 'url(#tail)' : '#1f4e79'}
          />
        )
      })}
      <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="#66707c" />
      <line x1={x(cut)} x2={x(cut)} y1={pad.t - 6} y2={H - pad.b} stroke="#18222d" strokeDasharray="3 3" />
      <text x={x(cut) - 6} y={pad.t - 14} textAnchor="end" fontSize="13" fontWeight="700" fill="#18222d">
        1-in-{odds} bad day: {pct(cut)}
      </text>
      <text x={x(cut) - 6} y={pad.t} textAnchor="end" fontSize="12" fill="#4a5663">
        {tailDays} days fell further
      </text>
      {ticks.map((t) => (
        <text key={t} x={x(t)} y={H - 8} textAnchor={t === lo ? 'start' : t === hi ? 'end' : 'middle'} fontSize="12" fill="#66707c" className="num">
          {pct(t)}
        </text>
      ))}
    </svg>
  )
}
