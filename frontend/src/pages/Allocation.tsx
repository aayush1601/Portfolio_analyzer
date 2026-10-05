import { useState } from 'react'
import { useApi, type Allocation, type Reference } from '../api'
import { pct, signedInr } from '../format'
import { Avatar, Card, Chip, Delta, IconArrow, Notes, Segmented, Status } from '../ui'

type Objective = Allocation['objective']
const OBJECTIVES: { value: Objective; label: string }[] = [
  { value: 'min_variance', label: 'Lowest risk' },
  { value: 'balanced', label: 'Balanced' },
]

function headline(a: Allocation) {
  const dv = a.target.volatility - a.current.volatility
  const verb = dv < -0.0005 ? 'cut' : dv > 0.0005 ? 'raise' : 'keep'
  const mix = a.objective === 'min_variance' ? 'The lowest-risk mix within the caps' : 'A balanced mix within the caps'
  return `${mix} would ${verb} volatility ${verb === 'keep' ? 'at' : 'from'} ${verb === 'keep' ? '' : `${pct(a.current.volatility)} to `}${pct(a.target.volatility)} a year.`
}

function Stat({ label, from, to, invert = false, neutral = false }: { label: string; from: number; to: number; invert?: boolean; neutral?: boolean }) {
  const better = invert ? to < from : to > from
  return (
    <div>
      <dt className="text-[0.8rem] text-ink-3">{label}</dt>
      <dd className="num flex items-center gap-1.5 text-[1.05rem] font-bold">
        <span className="text-ink-2">{pct(from)}</span>
        <IconArrow className="size-3.5 text-ink-3" />
        <span className={neutral || Math.abs(to - from) < 0.0005 ? 'text-ink' : better ? 'text-brand-ink' : 'text-loss'}>{pct(to)}</span>
      </dd>
    </div>
  )
}

/** Phase 10: a model allocation for this portfolio, research-framed. */
export function AllocationCard({ pid, reference }: { pid: string; reference: Reference }) {
  const [objective, setObjective] = useState<Objective>('min_variance')
  const q = useApi<Allocation>(`/portfolio/${pid}/optimize?objective=${objective}`)
  const name = (id: string) => reference.funds.find((f) => f.scheme_code === id)?.name ?? id
  return (
    <Card
      title={q.data ? headline(q.data) : 'Model allocation'}
      dek={
        objective === 'min_variance'
          ? 'Lowest risk needs no return forecast: it only spreads money so that holdings offset each other, within the caps.'
          : 'Balanced also uses past returns as a forecast (shrunk toward the average), so it leans toward recent winners. Treat it with more caution.'
      }
      aside={<Segmented<Objective> label="Allocation goal" options={OBJECTIVES} value={objective} onChange={setObjective} />}
      source="Hypothetical model portfolio for research, not a recommendation to trade. Long only; at most 20% per holding; cash kept at 5%; 15% per company and 25% per sector on look-through exposure. Estimated from 3 years of daily prices."
    >
      <Status q={q} what="the model allocation">
        {(a) => (
          <div className="space-y-5">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
              <Stat label="Volatility" from={a.current.volatility} to={a.target.volatility} invert />
              <Stat label="Expected return (model)" from={a.current.expected_return} to={a.target.expected_return} />
              <Stat label="Cash" from={a.cash_current} to={a.cash_target} neutral />
              <div>
                <dt className="text-[0.8rem] text-ink-3">Would change hands</dt>
                <dd className="num text-[1.05rem] font-bold">{pct(a.turnover, 0)}</dd>
              </div>
            </dl>
            <div>
              <h3 className="mb-2 text-[0.95rem] font-extrabold text-ink">Biggest changes</h3>
              <ul className="-mx-5 divide-y divide-line-soft border-y border-line sm:-mx-6">
                {a.items.slice(0, 10).map((i) => (
                  <li key={i.asset_id} className="flex items-center gap-3 px-5 py-2.5 sm:px-6">
                    <Avatar id={i.asset_id} label={i.asset_type === 'MF' ? name(i.asset_id) : i.asset_id} size="sm" />
                    <span className="min-w-0 flex-1 truncate font-bold">{i.asset_type === 'MF' ? name(i.asset_id) : i.asset_id}</span>
                    <span className="num hidden w-32 text-right text-[0.88rem] text-ink-2 sm:inline">
                      {pct(i.current)} → <span className="font-bold text-ink">{pct(i.target)}</span>
                    </span>
                    <Delta value={i.change} className="w-28 justify-end text-[0.88rem] font-bold">
                      {signedInr(i.change_inr)}
                    </Delta>
                  </li>
                ))}
              </ul>
            </div>
            {a.binding.length > 0 && (
              <div>
                <h3 className="mb-2 text-[0.95rem] font-extrabold text-ink">Limits the model ran into</h3>
                <div className="flex flex-wrap gap-1.5">
                  {a.binding.map((b) => (
                    <Chip key={b}>{b.replace(/\d{5,6}$/, (code) => name(code))}</Chip>
                  ))}
                </div>
              </div>
            )}
            {a.notes.length > 0 && (
              <div className="text-[0.82rem] text-ink-2">
                <Notes notes={a.notes} />
              </div>
            )}
          </div>
        )}
      </Status>
    </Card>
  )
}
