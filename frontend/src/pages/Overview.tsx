import { useState, type ReactNode } from 'react'
import { AllocationBar, Dumbbell, ValueChart } from '../charts'
import { api, useApi, type Exposure, type HoldingValue, type Loadable, type Reference, type Risk, type Snapshot, type ValueHistory } from '../api'
import { day, inr, inr2, pct, signedInr, signedPct } from '../format'
import { companyHeadline, unseenFunds } from '../insights'
import { reorder, slug } from '../motion'
import { Avatar, Button, Card, Chip, Delta, IconArrow, Segmented, Status } from '../ui'
import { HoldingsEditor } from './Holdings'

const RANGES = [
  { value: 30, label: '1M' },
  { value: 182, label: '6M' },
  { value: 365, label: '1Y' },
  { value: 1095, label: '3Y' },
  { value: 1826, label: '5Y' },
]

function RiskChip({ risk, pid }: { risk: Loadable<Risk>; pid: string }) {
  if (!risk.data && !risk.error) return null
  // Neutral on purpose: amber already means "through funds" on this screen.
  const label = risk.data ? `Risk ${risk.data.risk_score}/100 · ${risk.data.risk_band}` : 'Risk score unavailable'
  return (
    <a href={`#/risk/${pid}`} className="no-underline" aria-label={`${label}. Open risk`}>
      <Chip>
        {label} <IconArrow className="size-3" />
      </Chip>
    </a>
  )
}

function Hero({ s, risk, pid }: { s: Snapshot; risk: Loadable<Risk>; pid: string }) {
  const [days, setDays] = useState(365)
  const q = useApi<ValueHistory>(`/portfolio/${pid}/history?days=${days}`)
  const invested = s.total_value - s.total_pl
  const prev = s.total_value - s.daily_pl
  const pts = q.data?.points ?? []
  const rangeRet = pts.length > 1 ? pts[pts.length - 1].value / pts[0].value - 1 : null
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[0.85rem] font-bold text-ink-2">Current value</h1>
          <p className="num mt-0.5 text-[2.3rem] leading-tight font-extrabold tracking-[-0.02em] text-ink sm:text-[3.1rem]">{inr(s.total_value)}</p>
          <p className="mt-1 text-[0.85rem] text-ink-2">Prices as of {day(s.as_of)}</p>
        </div>
        <RiskChip risk={risk} pid={pid} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div>
          <dt className="text-[0.8rem] text-ink-3">Invested</dt>
          <dd className="num text-[1.05rem] font-bold">{inr(invested)}</dd>
        </div>
        <div>
          <dt className="text-[0.8rem] text-ink-3">Total returns</dt>
          <dd className="text-[1.05rem] font-bold">
            <Delta value={s.total_pl}>
              {signedInr(s.total_pl)} ({signedPct(invested ? s.total_pl / invested : 0)})
            </Delta>
          </dd>
        </div>
        <div>
          <dt className="text-[0.8rem] text-ink-3">1D returns</dt>
          <dd className="text-[1.05rem] font-bold">
            <Delta value={s.daily_pl}>
              {signedInr(s.daily_pl)} ({signedPct(prev ? s.daily_pl / prev : 0, 2)})
            </Delta>
          </dd>
        </div>
      </dl>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line-soft pt-5">
        <p className="text-[0.88rem] text-ink-2">
          {rangeRet === null ? (
            'Value history'
          ) : (
            <>
              Today’s holdings, held over the last {RANGES.find((r) => r.value === days)!.label}, would have moved{' '}
              <Delta value={rangeRet} className="font-bold">{signedPct(rangeRet)}</Delta>
            </>
          )}
        </p>
        <Segmented label="Time range" options={RANGES} value={days} onChange={setDays} />
      </div>
      <div className="mt-3">
        <Status q={q} what="value history">
          {(h) => <ValueChart points={h.points} invested={h.invested} />}
        </Status>
      </div>
      <p className="mt-2 text-[0.85rem] text-ink-2">Today’s holdings priced on past dates, not your actual trades, so this differs from total returns above.</p>
    </Card>
  )
}

type Mode = 'hold' | 'own'

function HoldingRow({ h, reference }: { h: HoldingValue; reference: Reference }) {
  const fund = h.asset_type === 'MF' ? reference.funds.find((f) => f.scheme_code === h.asset_id) : null
  const name = h.asset_type === 'CASH' ? 'Cash' : fund ? fund.name : h.asset_id
  const qty = h.quantity.toLocaleString('en-IN')
  // Each half stays whole, so narrow screens break at the dot rather than inside a figure.
  const pair = (a: string, b: string): ReactNode => (
    <>
      <span className="whitespace-nowrap">{a}</span> · <span className="whitespace-nowrap">{b}</span>
    </>
  )
  const sub =
    h.asset_type === 'CASH'
      ? 'Indian rupees'
      : h.asset_type === 'MF'
        ? pair(`${qty} units`, `Avg NAV ${inr2(h.avg_cost)}`)
        : pair(`${qty} shares`, `Avg ${inr2(h.avg_cost)}`)
  const cost = h.quantity * h.avg_cost
  return (
    <li className="flex items-center gap-3 px-5 py-3.5 sm:px-6" style={{ viewTransitionName: `own-${slug(h.asset_id)}` }}>
      <Avatar id={h.asset_id} label={h.asset_type === 'STOCK' ? h.asset_id : name} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold text-ink">{name}</p>
        <p className="text-[0.82rem] text-ink-2">{sub}</p>
      </div>
      <p className="num hidden w-24 text-right text-[0.9rem] font-bold sm:block">{pct(h.weight)}</p>
      <div className="w-36 text-right">
        <p className="num font-bold text-ink">{inr(h.value)}</p>
        {h.asset_type === 'CASH' ? (
          <p className="text-[0.82rem] text-ink-2">–</p>
        ) : (
          <Delta value={h.pl} className="text-[0.82rem] font-bold">
            {signedInr(h.pl)} ({signedPct(cost ? h.pl / cost : 0)})
          </Delta>
        )}
      </div>
    </li>
  )
}

function OwnRow({ id, title, sub, direct, effective, max, unseen, note }: { id: string; title: string; sub: string; direct: number; effective: number; max: number; unseen?: boolean; note?: string }) {
  const via = effective - direct
  const bar = (where: string) => (
    <div className={`relative h-2 rounded-full bg-line-soft ${where}`} aria-hidden>
      {unseen ? (
        <div className="hatch-unmapped absolute inset-y-0 left-0 rounded-full" style={{ width: `${(effective / max) * 100}%` }} />
      ) : (
        <>
          <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${(direct / max) * 100}%` }} />
          {via > 0.0005 && (
            <div className="hatch-via absolute -inset-y-px rounded-r-full" style={{ left: `${(direct / max) * 100}%`, width: `${(via / max) * 100}%` }} />
          )}
        </>
      )}
    </div>
  )
  return (
    <li className="flex items-center gap-3 px-5 py-3.5 sm:px-6" style={{ viewTransitionName: `own-${slug(id)}` }}>
      <Avatar id={id} label={unseen ? title : id} />
      <div className="min-w-0 flex-1">
        <p className={`truncate font-bold ${unseen ? 'text-ink-2 italic' : 'text-ink'}`}>{title}</p>
        <p className="truncate text-[0.82rem] text-ink-2">{sub}</p>
        {bar('mt-1.5 md:hidden')}
      </div>
      {bar('hidden w-40 md:block')}
      <div className="w-28 text-right">
        <p className={`num font-bold ${unseen ? 'text-ink-2' : 'text-ink'}`}>{pct(effective)}</p>
        <p className="text-[0.8rem] text-ink-2">{note ?? (unseen ? 'not yet visible' : direct < 0.0005 ? 'via funds only' : via > 0.0005 ? `${pct(direct)} direct` : 'direct only')}</p>
      </div>
    </li>
  )
}

/** The holdings view lives in the URL (#/overview/<pid>?view=own) so a demo or report figure can link to it. */
function useViewParam(): [Mode, (m: Mode) => void] {
  const read = (): Mode => (new URLSearchParams(window.location.hash.split('?')[1]).get('view') === 'own' ? 'own' : 'hold')
  const [mode, setMode] = useState<Mode>(read)
  const set = (m: Mode) => {
    const base = window.location.hash.split('?')[0] || '#/overview'
    history.replaceState(null, '', m === 'own' ? `${base}?view=own` : base)
    reorder(() => setMode(m))
  }
  return [mode, set]
}

function HoldingsList({
  s,
  exposure,
  reference,
  mode,
  setMode,
  onEdit,
}: {
  s: Snapshot
  exposure: Loadable<Exposure>
  reference: Reference
  mode: Mode
  setMode: (m: Mode) => void
  onEdit: () => void
}) {
  const held = [...s.holdings].sort((a, b) => b.value - a.value)
  const cash = s.holdings.filter((h) => h.asset_type === 'CASH').reduce((a, h) => a + h.weight, 0)
  const head = 'hidden items-center gap-3 px-5 pb-2 text-[0.82rem] font-bold text-ink-2 sm:flex sm:px-6'

  function own(e: Exposure) {
    const unseen = unseenFunds(e, s, reference)
    // Mapped funds still hold companies outside the research universe (or clubbed under 1%): show that share
    // rather than letting the rows fall short of 100%.
    const rest = e.unmapped - unseen.reduce((a, u) => a + u.weight, 0)
    const ownMax = Math.max(0.0001, ...e.companies.map((c) => c.effective), ...unseen.map((u) => u.weight), rest)
    return (
      <>
        <div className={head}>
          <span className="w-10" />
          <span className="flex-1">Company</span>
          <span className="hidden w-40 md:block">Direct, then via funds</span>
          <span className="w-28 text-right">Effective</span>
        </div>
        <ul className="divide-y divide-line-soft border-t border-line">
          {e.companies.map((c) => (
            <OwnRow
              key={c.symbol}
              id={c.symbol}
              title={c.symbol}
              sub={reference.stocks.find((x) => x.symbol === c.symbol)?.sector ?? c.sector}
              direct={c.direct}
              effective={c.effective}
              max={ownMax}
            />
          ))}
          {unseen.map((u) => (
            <OwnRow key={u.id} id={u.id} title={u.label} sub="Holdings disclosure not loaded yet" direct={0} effective={u.weight} max={ownMax} unseen />
          ))}
          {rest > 0.0005 && (
            <OwnRow
              id="other-in-funds"
              title="Other companies inside your funds"
              sub="Outside the NIFTY 50 research universe, or under 1% and not itemised"
              direct={0}
              effective={rest}
              max={ownMax}
              unseen
              note="outside universe"
            />
          )}
          {cash > 0.0005 && (
            <li className="px-5 py-3 text-[0.85rem] text-ink-2 sm:px-6">
              Cash, {pct(cash)}, isn’t a company, so it isn’t listed. With it, the rows add up to 100%.
            </li>
          )}
        </ul>
      </>
    )
  }

  return (
    <section id="holdings" className="scroll-mt-4 rounded-[var(--radius-card)] border border-line bg-panel shadow-[var(--shadow-card)]">
      <header className="px-5 pt-5 pb-4 sm:px-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-[1.08rem] font-bold text-ink sm:text-[1.15rem]">
              {mode === 'hold' ? `Holdings (${s.holdings.length})` : 'What you really own'}
            </h2>
            <p className="mt-0.5 text-[0.88rem] text-ink-2">
              {mode === 'hold' ? 'As your statement shows them.' : 'Every fund opened up into the companies inside it, ranked by effective exposure.'}
            </p>
          </div>
          <Button className="no-print shrink-0" onClick={onEdit}>
            Edit
          </Button>
        </div>
        <div className="mt-4">
          <Segmented<Mode>
            size="lg"
            label="Holdings view"
            options={[
              { value: 'hold', label: 'What you hold' },
              { value: 'own', label: 'What you really own' },
            ]}
            value={mode}
            onChange={setMode}
          />
        </div>
        <p className="sr-only" aria-live="polite">
          {mode === 'own' ? 'Showing what you really own, ranked by effective exposure.' : 'Showing holdings as your statement lists them.'}
        </p>
      </header>
      {mode === 'hold' ? (
        <>
          <div className={head}>
            <span className="w-10" />
            <span className="flex-1">Holding</span>
            <span className="w-24 text-right">Weight</span>
            <span className="w-36 text-right">Value, returns</span>
          </div>
          <ul className="divide-y divide-line-soft border-t border-line">
            {held.map((h) => (
              <HoldingRow key={h.asset_type + h.asset_id} h={h} reference={reference} />
            ))}
          </ul>
        </>
      ) : (
        <div className="min-w-0">
          {exposure.data ? (
            own(exposure.data)
          ) : (
            <div className="border-t border-line p-5 sm:p-6">
              <Status q={exposure} what="look-through exposure">
                {() => null}
              </Status>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

/** The look-through finding, with its figure: the companies your funds add most to. */
function Finding({ e, s, reference, pid, onShowOwn }: { e: Exposure; s: Snapshot; reference: Reference; pid: string; onShowOwn: () => void }) {
  const head = companyHeadline(e)
  const gaps = [...e.companies].filter((c) => c.indirect > 0.0005).sort((a, b) => b.indirect - a.indirect).slice(0, 3)
  const unseen = gaps.length ? [] : unseenFunds(e, s, reference)
  return (
    <Card title={head.title}>
      <p className="text-[0.88rem] text-ink-2">{head.dek}</p>
      {(gaps.length > 0 || unseen.length > 0) && (
        <div className="mt-4">
          <Dumbbell compact rows={gaps} cap={reference.caps.company} unseen={unseen} />
        </div>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Button variant="primary" className="no-print" onClick={onShowOwn}>
          Re-rank holdings by what you own
        </Button>
        <a href={`#/look-through/${pid}`} className="inline-flex items-center gap-1 text-[0.88rem] font-bold text-accent-ink">
          Full look-through <IconArrow className="size-3.5" />
        </a>
      </div>
    </Card>
  )
}

export function Overview({
  snap,
  exposure,
  risk,
  reference,
  pid,
  onSaved,
}: {
  snap: Snapshot
  exposure: Loadable<Exposure>
  risk: Loadable<Risk>
  reference: Reference
  pid: string
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [mode, setMode] = useViewParam()
  const weightOf = (t: string) => snap.holdings.filter((h) => h.asset_type === t).reduce((a, h) => a + h.weight, 0)

  if (editing)
    return (
      <Card title="Edit holdings" dek="Only NIFTY 50 stocks and the 15 research-universe funds can be added. Average cost is per share or unit, in today’s split-adjusted terms.">
        <HoldingsEditor
          initial={snap.holdings}
          reference={reference}
          onCancel={() => setEditing(false)}
          onSubmit={async (holdings) => {
            await api(`/portfolio/${pid}/holdings`, { method: 'PUT', body: JSON.stringify(holdings) })
            setEditing(false)
            onSaved()
          }}
        />
      </Card>
    )

  const showOwn = () => {
    setMode('own')
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById('holdings')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Hero s={snap} risk={risk} pid={pid} />
      <div className="grid content-start gap-5">
        <Status q={exposure} what="look-through exposure">
          {(e) => <Finding e={e} s={snap} reference={reference} pid={pid} onShowOwn={showOwn} />}
        </Status>
        <Card title="Allocation">
          <AllocationBar
            parts={[
              { label: 'Stocks', weight: weightOf('STOCK'), className: 'bg-accent' },
              { label: 'Mutual funds', weight: weightOf('MF'), className: 'hatch-via' },
              { label: 'Cash', weight: weightOf('CASH'), className: 'bg-ink-3/40' },
            ]}
          />
        </Card>
      </div>
      <div className="lg:col-span-2">
        <HoldingsList s={snap} exposure={exposure} reference={reference} mode={mode} setMode={setMode} onEdit={() => setEditing(true)} />
      </div>
    </div>
  )
}
