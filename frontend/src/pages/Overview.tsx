import { useState } from 'react'
import { AllocationBar, ValueChart } from '../charts'
import { api, useApi, type Exposure, type HoldingValue, type Reference, type Risk, type Snapshot, type ValueHistory } from '../api'
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

const bandTone = (b: string) => (b === 'Low' ? 'gain' : b === 'High' ? 'loss' : 'via') as 'gain' | 'loss' | 'via'

function Hero({ s, risk, pid }: { s: Snapshot; risk: Risk | null; pid: string }) {
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
          <p className="text-[0.85rem] font-bold text-ink-2">Current value</p>
          <p className="num mt-0.5 text-[2.3rem] leading-tight font-extrabold tracking-[-0.02em] text-ink sm:text-[3.1rem]">{inr(s.total_value)}</p>
          <p className="mt-1 text-[0.78rem] text-ink-3">Prices to {day(s.as_of)} · news near-real-time</p>
        </div>
        {risk && (
          <a href={`#/risk/${pid}`} className="no-underline" aria-label={`Risk score ${risk.risk_score}, ${risk.risk_band}. Open risk`}>
            <Chip tone={bandTone(risk.risk_band)}>
              Risk {risk.risk_score} · {risk.risk_band}
            </Chip>
          </a>
        )}
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
              This mix would have moved <Delta value={rangeRet} className="font-bold">{signedPct(rangeRet)}</Delta> over{' '}
              {RANGES.find((r) => r.value === days)!.label}
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
      <p className="mt-2 text-[0.75rem] text-ink-3">Today’s holdings valued on past dates: how this mix would have moved, not your actual trades.</p>
    </Card>
  )
}

type Mode = 'hold' | 'own'

function HoldingRow({ h, reference }: { h: HoldingValue; reference: Reference }) {
  const fund = h.asset_type === 'MF' ? reference.funds.find((f) => f.scheme_code === h.asset_id) : null
  const name = h.asset_type === 'CASH' ? 'Cash' : fund ? fund.name : h.asset_id
  const sub =
    h.asset_type === 'CASH'
      ? 'Indian rupees'
      : h.asset_type === 'MF'
        ? `${h.quantity.toLocaleString('en-IN')} units · Avg NAV ${inr2(h.avg_cost)}`
        : `${h.quantity.toLocaleString('en-IN')} shares · Avg ${inr2(h.avg_cost)}`
  const cost = h.quantity * h.avg_cost
  return (
    <li className="flex items-center gap-3 px-5 py-3.5 sm:px-6" style={{ viewTransitionName: `own-${slug(h.asset_id)}` }}>
      <Avatar id={h.asset_id} label={h.asset_type === 'STOCK' ? h.asset_id : name} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold text-ink">{name}</p>
        <p className="text-[0.8rem] text-ink-3">{sub}</p>
      </div>
      <div className="hidden w-24 text-right sm:block">
        <p className="text-[0.75rem] text-ink-3">Weight</p>
        <p className="num text-[0.9rem] font-bold">{pct(h.weight)}</p>
      </div>
      <div className="w-36 text-right">
        <p className="num font-bold text-ink">{inr(h.value)}</p>
        {h.asset_type === 'CASH' ? (
          <p className="text-[0.8rem] text-ink-3">–</p>
        ) : (
          <Delta value={h.pl} className="text-[0.8rem] font-bold">
            {signedInr(h.pl)} ({signedPct(cost ? h.pl / cost : 0)})
          </Delta>
        )}
      </div>
    </li>
  )
}

function OwnRow({ id, title, sub, direct, effective, max, unseen }: { id: string; title: string; sub: string; direct: number; effective: number; max: number; unseen?: boolean }) {
  const via = effective - direct
  return (
    <li className="flex items-center gap-3 px-5 py-3.5 sm:px-6" style={{ viewTransitionName: `own-${slug(id)}` }}>
      <Avatar id={id} label={unseen ? title : id} />
      <div className="min-w-0 flex-1">
        <p className={`truncate font-bold ${unseen ? 'text-ink-2 italic' : 'text-ink'}`}>{title}</p>
        <p className="truncate text-[0.8rem] text-ink-3">{sub}</p>
      </div>
      <div className="relative hidden h-2 w-40 rounded-full bg-line-soft md:block" aria-hidden>
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
      <div className="w-24 text-right">
        <p className={`num font-bold ${unseen ? 'text-ink-2' : 'text-ink'}`}>{pct(effective)}</p>
        <p className="text-[0.75rem] text-ink-3">{unseen ? 'not yet visible' : via > 0.0005 ? `${pct(direct)} direct` : 'direct only'}</p>
      </div>
    </li>
  )
}

function HoldingsList({ s, exposure, reference, onEdit }: { s: Snapshot; exposure: Exposure | null; reference: Reference; onEdit: () => void }) {
  const [mode, setMode] = useState<Mode>('hold')
  const unseen = exposure ? unseenFunds(exposure, s, reference) : []
  const ownMax = Math.max(0.0001, ...(exposure?.companies.map((c) => c.effective) ?? []), ...unseen.map((u) => u.weight))
  const held = [...s.holdings].sort((a, b) => b.value - a.value)
  return (
    <section className="rounded-[var(--radius-card)] border border-line bg-panel shadow-[var(--shadow-card)]">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 pb-4 sm:px-6">
        <div>
          <h2 className="text-[1.08rem] font-bold text-ink sm:text-[1.15rem]">
            {mode === 'hold' ? `Holdings (${s.holdings.length})` : 'What you really own'}
          </h2>
          <p className="mt-0.5 text-[0.85rem] text-ink-2">
            {mode === 'hold' ? 'As your statement shows them.' : 'Every fund opened up into the companies inside it.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented<Mode>
            label="Holdings view"
            options={[
              { value: 'hold', label: 'What you hold' },
              { value: 'own', label: 'What you really own' },
            ]}
            value={mode}
            onChange={(m) => reorder(() => setMode(m))}
          />
          <Button className="no-print" onClick={onEdit}>
            Edit
          </Button>
        </div>
      </header>
      <ul className="divide-y divide-line-soft border-t border-line">
        {mode === 'hold'
          ? held.map((h) => <HoldingRow key={h.asset_type + h.asset_id} h={h} reference={reference} />)
          : [
              ...(exposure?.companies ?? []).map((c) => (
                <OwnRow
                  key={c.symbol}
                  id={c.symbol}
                  title={c.symbol}
                  sub={reference.stocks.find((x) => x.symbol === c.symbol)?.sector ?? c.sector}
                  direct={c.direct}
                  effective={c.effective}
                  max={ownMax}
                />
              )),
              ...unseen.map((u) => (
                <OwnRow key={u.id} id={u.id} title={u.label} sub="Holdings disclosure not loaded yet" direct={0} effective={u.weight} max={ownMax} unseen />
              )),
            ]}
      </ul>
    </section>
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
  exposure: Exposure | null
  risk: Risk | null
  reference: Reference
  pid: string
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const weightOf = (t: string) => snap.holdings.filter((h) => h.asset_type === t).reduce((a, h) => a + h.weight, 0)
  const head = exposure ? companyHeadline(exposure) : null

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

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Hero s={snap} risk={risk} pid={pid} />
      <div className="grid content-start gap-5">
        {head && (
          <Card title={head.title}>
            <p className="text-[0.88rem] text-ink-2">{head.dek}</p>
            <a
              href={`#/look-through/${pid}`}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-accent-soft px-3 py-2 text-[0.88rem] font-bold text-accent-ink no-underline hover:bg-accent hover:text-white"
            >
              See what you really own <IconArrow className="size-3.5" />
            </a>
          </Card>
        )}
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
        <HoldingsList s={snap} exposure={exposure} reference={reference} onEdit={() => setEditing(true)} />
      </div>
    </div>
  )
}
