import { useId, useState, type ReactNode } from 'react'
import { day, inr, pct, pts, signedPct } from './format'
import { IconAlert, Plate } from './ui'

const UNMAPPED = 'Other/Unmapped'
const at = (v: number, max: number) => `${Math.min(100, (v / max) * 100)}%`

// ---------- value history (the hero chart) ----------
export function ValueChart({ points, invested }: { points: { date: string; value: number }[]; invested: number }) {
  const gid = useId().replace(/:/g, '')
  const [hover, setHover] = useState<number | null>(null)
  if (points.length < 2) return <p className="py-10 text-center text-ink-3">Not enough price history for this range yet.</p>
  const vals = points.map((p) => p.value)
  const lo0 = Math.min(...vals, invested), hi0 = Math.max(...vals, invested)
  const padY = (hi0 - lo0) * 0.12 || hi0 * 0.02
  const lo = lo0 - padY, hi = hi0 + padY
  const W = 1000, H = 260
  const x = (i: number) => (i / (points.length - 1)) * W
  const y = (v: number) => H - ((v - lo) / (hi - lo)) * H
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join('')
  const up = vals[vals.length - 1] >= vals[0]
  const stroke = up ? 'var(--color-brand)' : 'var(--color-loss)'
  const h = hover === null ? null : points[hover]
  const yInvested = (y(invested) / H) * 100

  function onMove(e: React.PointerEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect()
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
    setHover(Math.round(f * (points.length - 1)))
  }

  return (
    <figure>
      <div
        className="relative h-56 touch-none select-none sm:h-64"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label={`Value from ${inr(vals[0])} on ${day(points[0].date)} to ${inr(vals[vals.length - 1])} on ${day(points[points.length - 1].date)}`}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" aria-hidden>
          <defs>
            <linearGradient id={`fill-${gid}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={stroke} stopOpacity="0.16" />
              <stop offset="1" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={`${line}L${W},${H}L0,${H}Z`} fill={`url(#fill-${gid})`} />
          <path
            d={line}
            fill="none"
            stroke={stroke}
            strokeWidth={2.25}
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
          />
        </svg>
        {/* invested baseline, labelled on the chart */}
        <div aria-hidden className="absolute inset-x-0 border-t border-dashed border-ink-3/60" style={{ top: `${yInvested}%` }}>
          <span className="absolute right-0 -translate-y-full pb-0.5 text-[0.72rem] font-bold text-ink-3">Invested {inr(invested)}</span>
        </div>
        {h && hover !== null && (
          <>
            <div aria-hidden className="absolute inset-y-0 border-l border-ink/20" style={{ left: `${(hover / (points.length - 1)) * 100}%` }} />
            <div
              aria-hidden
              className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-panel shadow-[var(--shadow-card)]"
              style={{ left: `${(hover / (points.length - 1)) * 100}%`, top: `${(y(h.value) / H) * 100}%`, background: stroke }}
            />
            <div
              className="pointer-events-none absolute top-0 z-10 rounded-lg bg-ink px-2.5 py-1.5 text-[0.78rem] text-white shadow-[var(--shadow-card)]"
              style={
                hover / (points.length - 1) > 0.7
                  ? { right: `${100 - (hover / (points.length - 1)) * 100}%`, marginRight: 8 }
                  : { left: `${(hover / (points.length - 1)) * 100}%`, marginLeft: 8 }
              }
            >
              <span className="num block font-bold">{inr(h.value)}</span>
              <span className="text-white/75">{day(h.date)}</span>
            </div>
          </>
        )}
      </div>
      <figcaption className="mt-2 flex justify-between text-[0.75rem] text-ink-3">
        <span>{day(points[0].date)}</span>
        <span>{day(points[points.length - 1].date)}</span>
      </figcaption>
    </figure>
  )
}

// ---------- riskometer ----------
/** A semicircle riskometer, the gauge every Indian fund factsheet carries; needle at the 0–100 score. */
export function Riskometer({ score, band }: { score: number; band: string }) {
  const bands = [
    { name: 'Low', from: 0, to: 33, fill: 'var(--color-brand)' },
    { name: 'Moderate', from: 33, to: 66, fill: 'var(--color-via)' },
    { name: 'High', from: 66, to: 100, fill: 'var(--color-loss)' },
  ]
  const cx = 120, cy = 118, r = 96, w = 22
  const pt = (s: number, rad: number) => {
    const a = Math.PI * (1 - s / 100)
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)]
  }
  const arc = (a: number, b: number) => {
    const [x1, y1] = pt(a, r), [x2, y2] = pt(b, r), [x3, y3] = pt(b, r - w), [x4, y4] = pt(a, r - w)
    return `M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2} L${x3},${y3} A${r - w},${r - w} 0 0 0 ${x4},${y4} Z`
  }
  const angle = -90 + (score / 100) * 180
  return (
    <figure className="flex flex-col items-center" role="img" aria-label={`Risk score ${score} of 100, ${band}`}>
      <svg viewBox="0 0 240 132" className="w-full max-w-[260px]" aria-hidden>
        {bands.map((b) => (
          <path key={b.name} d={arc(b.from + 0.6, b.to - 0.6)} fill={b.fill} opacity={b.name === band ? 1 : 0.28} />
        ))}
        <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: `${cx}px ${cy}px`, transition: 'transform 600ms cubic-bezier(0.16, 1, 0.3, 1)' }}>
          <path d={`M${cx - 4},${cy} L${cx},${cy - r + 30} L${cx + 4},${cy} Z`} fill="var(--color-ink)" />
        </g>
        <circle cx={cx} cy={cy} r="8" fill="var(--color-ink)" />
        <circle cx={cx} cy={cy} r="3" fill="var(--color-panel)" />
      </svg>
      <div className="-mt-1 flex w-full max-w-[260px] justify-between px-[4%] text-[0.72rem] font-bold text-ink-3">
        <span>Low</span>
        <span>High</span>
      </div>
    </figure>
  )
}

// ---------- look-through ----------
function Track({ max, cap, children }: { max: number; cap?: number; children: ReactNode }) {
  return (
    <div className="relative h-5">
      <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line-soft" />
      {children}
      {cap !== undefined && cap < max && (
        <div aria-hidden className="absolute -inset-y-1 border-l border-dashed border-ink-3" style={{ left: `${(cap / max) * 100}%` }} />
      )}
    </div>
  )
}

/**
 * The look-through dumbbell. Indigo: what you hold directly. Amber hatch: what your funds add on top.
 * The ring is effective exposure; it travels from the direct dot to where you really are.
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
  const grid = 'grid grid-cols-[1fr_5.5rem] items-center gap-x-3 gap-y-0.5 sm:grid-cols-[minmax(7rem,11rem)_1fr_6.5rem]'
  return (
    <div role="list" className="space-y-2">
      <div className={`${grid} text-[0.72rem] font-bold text-ink-3`}>
        <span className="hidden sm:block" />
        <div className="relative h-4">
          <span className="absolute left-0">0%</span>
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: at(cap, max) }}>
            {pct(cap, 0)} cap
          </span>
        </div>
        <span className="text-right">Effective</span>
      </div>
      {rows.map((r, i) => {
        const breach = r.effective > cap
        const via = r.effective - r.direct
        return (
          <div role="listitem" key={r.symbol} className={grid} aria-label={`${r.symbol}: direct ${pct(r.direct)}, effective ${pct(r.effective)}`}>
            <span className="col-span-2 truncate text-[0.9rem] sm:col-span-1">
              <Plate id={r.symbol} compact />
            </span>
            <Track max={max} cap={cap}>
              <div className="draw-x absolute inset-y-[6px] left-0 rounded-full bg-accent" style={{ width: at(r.direct, max), animationDelay: `${i * 40}ms` }} />
              {via > 0.0005 && (
                <div
                  className="draw-x hatch-via absolute inset-y-[3px] rounded-r-full outline outline-1 outline-via"
                  style={{ left: at(r.direct, max), width: at(via, max), animationDelay: `${i * 40 + 200}ms` }}
                />
              )}
              {r.direct > 0 && (
                <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent ring-2 ring-panel" style={{ left: at(r.direct, max) }} />
              )}
              {via > 0.0005 ? (
                <div className="absolute inset-y-0 [container-type:inline-size]" style={{ left: at(r.direct, max), width: at(via, max) }}>
                  <div
                    className="travel-x absolute top-1/2 left-full size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-panel"
                    style={{ animationDelay: `${i * 40 + 200}ms` }}
                  />
                </div>
              ) : (
                <div
                  className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-panel transition-[left] duration-300 ease-out"
                  style={{ left: at(r.effective, max) }}
                />
              )}
            </Track>
            <span className={`num text-right text-[0.9rem] font-bold ${breach ? 'text-loss' : 'text-ink'}`}>
              {breach && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
              {pct(r.effective)}
              {via > 0.0005 && <span className="block text-[0.72rem] font-bold text-via-ink">{pts(via)} via funds</span>}
            </span>
          </div>
        )
      })}
      {unseen.map((u) => (
        <div role="listitem" key={u.label} className={`${grid} border-t border-dashed border-line pt-2`} aria-label={`${u.label}: ${pct(u.weight)}, holdings not yet visible`}>
          <span className="col-span-2 truncate text-[0.9rem] text-ink-2 italic sm:col-span-1" title={u.label}>
            {u.label}
          </span>
          <Track max={max} cap={cap}>
            <div className="draw-x hatch-unmapped absolute inset-y-[3px] left-0 rounded-full" style={{ width: at(u.weight, max) }} />
          </Track>
          <span className="num text-right text-[0.9rem] text-ink-2">
            {pct(u.weight)}
            <span className="block text-[0.72rem] text-ink-3">not yet visible</span>
          </span>
        </div>
      ))}
    </div>
  )
}

/** Sector exposure: direct (indigo) plus what funds add (hatched), against the sector cap. */
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
    <div className="space-y-3">
      {rows.map((r, i) => {
        const unmapped = r.sector === UNMAPPED
        const breach = !unmapped && r.effective > cap
        return (
          <div key={r.sector}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-[0.85rem]">
              <span className={unmapped ? 'text-ink-2 italic' : 'font-bold text-ink'}>{unmapped ? unmappedLabel : r.sector}</span>
              <span className={`num font-bold ${breach ? 'text-loss' : 'text-ink-2'}`}>
                {breach && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
                {pct(r.effective)}
              </span>
            </div>
            <Track max={max} cap={unmapped ? undefined : cap}>
              {unmapped ? (
                <div className="draw-x hatch-unmapped absolute inset-y-1 left-0 rounded-full" style={{ width: at(r.effective, max) }} />
              ) : (
                <>
                  <div className="draw-x absolute inset-y-1 left-0 rounded-full bg-accent" style={{ width: at(r.direct, max), animationDelay: `${i * 40}ms` }} />
                  {r.effective - r.direct > 0.0005 && (
                    <div
                      className="draw-x hatch-via absolute inset-y-0.5 rounded-r-full outline outline-1 outline-via"
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

/** Allocation: one rounded bar split by asset class, with a legend list. */
export function AllocationBar({ parts }: { parts: { label: string; weight: number; className: string }[] }) {
  const shown = parts.filter((p) => p.weight > 0)
  return (
    <div>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full" role="img" aria-label={shown.map((p) => `${p.label} ${pct(p.weight)}`).join(', ')}>
        {shown.map((p, i) => (
          <div key={p.label} className={`draw-x h-full ${p.className}`} style={{ width: `${p.weight * 100}%`, animationDelay: `${i * 60}ms` }} />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5 text-[0.88rem]">
        {shown.map((p) => (
          <li key={p.label} className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 text-ink-2">
              <span aria-hidden className={`h-2.5 w-3.5 rounded-sm ${p.className}`} />
              {p.label}
            </span>
            <span className="num font-bold">{pct(p.weight)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Daily returns as a histogram; days beyond VaR are the hatched tail, annotated on the chart. */
export function TailHistogram({ edges, counts, varLoss, odds }: { edges: number[]; counts: number[]; varLoss: number; odds: number }) {
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
          className={`absolute bottom-0 text-[0.8rem] leading-tight transition-[left,right] duration-300 ease-out ${left < 50 ? 'pl-2 text-left' : 'pr-2 text-right'}`}
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
              <rect width="1.6" height="3" fill="var(--color-loss-soft)" />
              <rect width="0.6" height="3" fill="var(--color-loss)" />
            </pattern>
          </defs>
          {counts.map((c, i) =>
            inTail(i) ? (
              // hatched tail bars keep real geometry so the pattern is never squashed
              <rect key={i} x={xp(edges[i]) + 0.15} y={100 - (c / top) * 100} width={Math.max(0, xp(edges[i + 1]) - xp(edges[i]) - 0.3)} height={(c / top) * 100} fill="url(#tail)" />
            ) : (
              <rect
                key={i}
                x={xp(edges[i]) + 0.15}
                y={0}
                width={Math.max(0, xp(edges[i + 1]) - xp(edges[i]) - 0.3)}
                height={100}
                fill="var(--color-accent)"
                style={{ transformBox: 'fill-box', transformOrigin: 'bottom', transform: `scaleY(${c / top})`, transition: 'transform 320ms cubic-bezier(0.16, 1, 0.3, 1)' }}
              />
            ),
          )}
        </svg>
        <div className="absolute -top-2 bottom-0 border-l border-dashed border-ink transition-[left] duration-300 ease-out" style={{ left: `${left}%` }} />
      </div>
      <div className="num relative h-5 border-t border-ink-3 text-[0.75rem] text-ink-3">
        <span className="absolute left-0 pt-0.5">{signedPct(lo)}</span>
        {lo < 0 && hi > 0 && (
          <span className="absolute -translate-x-1/2 pt-0.5" style={{ left: `${xp(0)}%` }}>
            0%
          </span>
        )}
        <span className="absolute right-0 pt-0.5">{signedPct(hi)}</span>
      </div>
    </figure>
  )
}

/** Diverging bar around zero. Direction carries the sign; colour backs it up. */
export function SignedBar({ value, max, label }: { value: number; max: number; label: string }) {
  const w = `${Math.min(50, (Math.abs(value) / (max || 1)) * 50)}%`
  return (
    <div className="relative h-2 w-full min-w-16" role="img" aria-label={label}>
      <div className="absolute inset-0 rounded-full bg-line-soft" />
      <div className="absolute inset-y-0 left-1/2 w-px bg-ink-3" />
      <div className={`absolute inset-y-0 ${value >= 0 ? 'left-1/2 rounded-r-full bg-brand' : 'right-1/2 rounded-l-full bg-loss'}`} style={{ width: w }} />
    </div>
  )
}

/** 0–100 score as a rounded bar with its number. */
export function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-ink-3">n/a</span>
  return (
    <span className="inline-flex w-full items-center gap-2">
      <span className="relative h-1.5 flex-1 rounded-full bg-line-soft">
        <span className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${value}%` }} />
      </span>
      <span className="num w-8 text-right text-[0.85rem] font-bold">{Math.round(value)}</span>
    </span>
  )
}
