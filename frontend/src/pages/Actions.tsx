import { ScoreBar } from '../charts'
import { AllocationCard } from './Allocation'
import { useApi, type Recommendation, type Reference, type Recommendations } from '../api'
import { fixed, inr, pct } from '../format'
import { Avatar, Card, IconAlert, Notes, Plate, Status } from '../ui'

const COMPONENTS: [string, string][] = [
  ['news', 'News'],
  ['risk', 'Risk (higher = calmer)'],
  ['portfolio_fit', 'Portfolio fit'],
  ['allocation', 'Model allocation'],
  ['expected_return', 'Expected return'],
]
const RULE: Record<string, string> = { max_company_exposure: 'Single-company cap', max_sector_exposure: 'Sector cap' }
const ruleLabel = (c: string) => {
  const [rule, subject] = c.split(':')
  return `${RULE[rule] ?? rule}${subject ? ` (${subject})` : ''}`
}
// Research language, not trade buttons: the insight names the direction the evidence points.
const LABEL: Record<string, string> = { BUY: 'Add', INCREASE: 'Add', HOLD: 'Hold', REDUCE: 'Reduce', SWITCH: 'Switch' }
const PILL: Record<string, string> = {
  BUY: 'bg-brand-soft text-brand-ink',
  INCREASE: 'bg-brand-soft text-brand-ink',
  HOLD: 'bg-line-soft text-ink-2',
  REDUCE: 'bg-loss-soft text-loss',
  SWITCH: 'bg-accent-soft text-accent-ink',
}

function InsightPill({ action }: { action: string }) {
  return <span className={`inline-flex rounded-full px-3 py-1 text-[0.82rem] font-extrabold ${PILL[action] ?? PILL.HOLD}`}>{LABEL[action] ?? action}</span>
}

function summary(r: Recommendations) {
  const count = (a: string[]) => r.items.filter((i) => a.includes(i.action)).length
  const parts = [
    [['REDUCE'], 'to reduce'],
    [['SWITCH'], 'to switch'],
    [['BUY', 'INCREASE'], 'to add to'],
    [['HOLD'], 'to hold'],
  ] as const
  const text = parts
    .map(([a, w]) => [count([...a]), w] as const)
    .filter(([n]) => n > 0)
    .map(([n, w]) => `${n} ${w}`)
  const blocked = r.items.filter((i) => i.blocked_action).length
  return `${text.join(', ')}${blocked ? `; ${blocked} held back by a cap` : ''}.`
}

function InsightCard({ i, weights, fundName }: { i: Recommendation; weights: Record<string, number>; fundName: (c: string) => string }) {
  const label = i.asset_type === 'MF' ? fundName(i.asset_id) : i.asset_id
  return (
    <li className="grid gap-x-8 gap-y-4 px-5 py-5 sm:px-6 lg:grid-cols-[minmax(14rem,1fr)_minmax(15rem,1fr)_minmax(0,1.4fr)]">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <Avatar id={i.asset_id} label={label} />
          <div className="min-w-0">
            <p className="truncate text-[0.95rem]">
              <Plate id={i.asset_id} compact />
            </p>
            <p className="text-[0.78rem] text-ink-3">{i.asset_type === 'MF' ? 'Mutual fund' : 'Stock'}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {i.blocked_action && (
            <span className="relative px-1 text-[0.82rem] font-extrabold text-ink-3" title="What the scores proposed before a cap overrode it">
              {LABEL[i.blocked_action] ?? i.blocked_action}
              <span className="sr-only"> (overridden)</span>
              <span aria-hidden className="strike-draw absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2 bg-ink-3" />
            </span>
          )}
          <InsightPill action={i.action} />
          <span className="num text-[0.85rem] text-ink-2">score {fixed(i.final_score, 0)}</span>
        </div>
        {i.switch_to && (
          <p className="mt-2 text-[0.85rem] text-ink-2">
            Switch to <span className="font-bold text-ink">{fundName(i.switch_to)}</span>
          </p>
        )}
        {i.constraints_triggered.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {i.constraints_triggered.map((c) => (
              <li key={c} className="inline-flex items-center gap-1 rounded-full bg-loss-soft px-2.5 py-0.5 text-[0.75rem] font-bold text-loss">
                <IconAlert className="size-3" /> {ruleLabel(c)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <dl className="grid grid-cols-[9.5rem_1fr] content-start items-center gap-x-3 gap-y-2 text-[0.85rem]">
        {COMPONENTS.map(([k, name]) => (
          <div key={k} className="contents">
            <dt className="text-ink-2">
              {name}
              {weights[k] === 0 && <span className="block text-[0.72rem] text-ink-3">not weighted</span>}
            </dt>
            <dd>
              {k === 'expected_return' && i.components[k] === null ? (
                <span className="text-ink-3">{i.asset_type === 'MF' ? 'stocks only' : 'run the ML model'}</span>
              ) : (
                <ScoreBar value={i.components[k] ?? null} />
              )}
            </dd>
          </div>
        ))}
      </dl>
      <ul className="space-y-1.5 text-[0.88rem] text-ink">
        {i.reasons.map((x) => (
          <li key={x} className="flex gap-2">
            <span aria-hidden className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-accent" />
            {x}
          </li>
        ))}
      </ul>
    </li>
  )
}

export function Actions({ pid, reference }: { pid: string; reference: Reference }) {
  const q = useApi<Recommendations>(`/portfolio/${pid}/recommendations`)
  const fundName = (code: string) => reference.funds.find((f) => f.scheme_code === code)?.name ?? code
  return (
    <Status q={q} what="insights">
      {(r) => (
        <div className="space-y-5">
          <p className="rounded-[var(--radius-card)] border border-accent/20 bg-accent-soft px-5 py-3 text-[0.9rem] text-ink">
            <span className="font-extrabold">Research insights, not advice.</span> {r.disclaimer} Backtesting of these rules is still to come, and nothing
            here guarantees profit.
          </p>
          <AllocationCard pid={pid} reference={reference} />
          <Card
            title={`Of ${r.items.length} holdings: ${summary(r)}`}
            dek="Each score blends news, risk, how well the holding fits the portfolio and how far it sits from the model allocation, 0–100 (higher favours keeping or adding). Look-through caps can only make an insight more cautious; when one does, the original call stays visible."
            source={
              <>
                Rules version {r.config_version}; model allocation goal: {r.allocation_objective === 'balanced' ? 'balanced' : 'lowest risk'}. ≥ 65 add, ≤ 35 reduce, caps 15% per company and 25% per sector on effective exposure.
                {r.notes.length > 0 && (
                  <span className="mt-1 block">
                    <Notes notes={r.notes} />
                  </span>
                )}
              </>
            }
          >
            <ol className="-mx-5 divide-y divide-line-soft border-t border-line sm:-mx-6">
              {r.items.map((i) => (
                <InsightCard key={i.asset_id} i={i} weights={r.weights} fundName={fundName} />
              ))}
            </ol>
          </Card>
          {r.additions.length > 0 && (
            <Card
              title={`${r.additions.length} holding${r.additions.length === 1 ? '' : 's'} you don’t own that the model allocation would add`}
              dek="Where the money from the reductions above would go in the model allocation. Each keeps every look-through cap. Research output, not a recommendation to buy."
            >
              <ul className="-mx-5 divide-y divide-line-soft border-t border-line sm:-mx-6">
                {r.additions.map((a) => {
                  const label = a.asset_type === 'MF' ? fundName(a.asset_id) : a.asset_id
                  return (
                    <li key={a.asset_id} className="flex flex-wrap items-center gap-3 px-5 py-3 sm:px-6">
                      <Avatar id={a.asset_id} label={label} />
                      <div className="min-w-0 flex-1">
                        <p className="font-bold text-ink">
                          {label} <span className="text-[0.8rem] font-medium text-ink-3">{a.asset_type === 'MF' ? 'Mutual fund' : 'Stock'}</span>
                        </p>
                        <p className="text-[0.82rem] text-ink-2">{a.reasons.join(' · ')}</p>
                      </div>
                      <div className="text-right">
                        <p className="num font-bold text-brand-ink">{pct(a.target)}</p>
                        <p className="num text-[0.78rem] text-ink-3">about {inr(a.amount_inr)}</p>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </Card>
          )}
        </div>
      )}
    </Status>
  )
}
