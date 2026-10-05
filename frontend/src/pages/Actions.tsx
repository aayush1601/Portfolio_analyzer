import { ScoreBar } from '../charts'
import { useApi, type Reference, type Recommendations } from '../api'
import { Figure, IconAlert, Notes, Plate, Status } from '../ui'
import { fixed } from '../format'

const COMPONENTS: [string, string][] = [
  ['news', 'News'],
  ['risk', 'Risk (higher = calmer)'],
  ['portfolio_fit', 'Portfolio fit'],
  ['expected_return', 'Expected return'],
]
const RULE: Record<string, string> = {
  max_company_exposure: 'single-company cap',
  max_sector_exposure: 'sector cap',
}
const ruleLabel = (c: string) => {
  const [rule, subject] = c.split(':')
  return `${RULE[rule] ?? rule}${subject ? ` (${subject})` : ''}`
}

function Stamp({ action }: { action: string }) {
  const filled = action === 'BUY' || action === 'INCREASE'
  return (
    <span
      className={`inline-block rounded-[2px] border-2 px-2 py-0.5 text-[0.8rem] font-bold tracking-[0.06em] ${
        filled ? 'border-direct bg-direct text-panel' : action === 'HOLD' ? 'border-ink-3 text-ink-2' : 'border-ink text-ink'
      }`}
    >
      {action}
    </span>
  )
}

function summary(r: Recommendations) {
  const count = (a: string) => r.items.filter((i) => i.action === a).length
  const parts = [
    ['REDUCE', 'to reduce'],
    ['SWITCH', 'to switch'],
    ['BUY', 'to add to'],
    ['INCREASE', 'to add to'],
    ['HOLD', 'to hold'],
  ]
    .map(([a, w]) => [count(a), w] as const)
    .filter(([n]) => n > 0)
    .map(([n, w]) => `${n} ${w}`)
  const blocked = r.items.filter((i) => i.blocked_action).length
  return `${parts.join(', ')}${blocked ? `; ${blocked} held back by a cap` : ''}.`
}

export function Actions({ pid, reference }: { pid: string; reference: Reference }) {
  const q = useApi<Recommendations>(`/portfolio/${pid}/recommendations`)
  const fundName = (code: string) => reference.funds.find((f) => f.scheme_code === code)?.name ?? code
  return (
    <Status q={q} what="recommendations">
      {(r) => (
        <div className="space-y-5">
          <p className="border-y border-ink bg-panel px-5 py-2.5 text-[0.9rem] sm:px-6">
            <span className="font-semibold">Research output, not advice.</span> {r.disclaimer} Every action below is hypothetical and is evaluated by
            historical backtesting; nothing here guarantees profit.
          </p>
          <Figure
            title={`Of ${r.items.length} holdings: ${summary(r)}`}
            dek="Each score blends news, risk and how well the holding fits the portfolio, 0–100 (higher favours keeping or adding). Look-through caps can only make an action more cautious; when one does, the original call stays visible."
            source={
              <>
                Rules version {r.config_version} (config/recommendations.yaml): ≥ 65 add, ≤ 35 reduce, caps 15% per company and 25% per sector on effective exposure.
                {r.notes.length > 0 && <span className="mt-1 block"><Notes notes={r.notes} /></span>}
              </>
            }
          >
            <ol className="-mx-5 sm:-mx-6">
              {r.items.map((i) => (
                <li
                  key={i.asset_id}
                  className="grid gap-x-6 gap-y-3 border-b border-rule-soft px-5 py-4 last:border-b-0 sm:px-6 md:grid-cols-[minmax(12rem,1fr)_minmax(14rem,1.1fr)_minmax(0,1.6fr)]"
                >
                  <div className="min-w-0 space-y-2">
                    <div className="text-[0.95rem]">
                      <Plate id={i.asset_id} />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {i.blocked_action && (
                        <span className="relative rounded-[2px] border-2 border-transparent px-1 py-0.5 text-[0.8rem] font-bold tracking-[0.06em] text-ink-2" title="What the scores proposed before a cap overrode it">
                          {i.blocked_action}
                          <span className="sr-only"> (overridden)</span>
                          <span aria-hidden className="strike-draw absolute inset-x-0.5 top-1/2 h-[2px] -translate-y-1/2 bg-ink-2" />
                        </span>
                      )}
                      <Stamp action={i.action} />
                      <span className="num text-[0.9rem] text-ink-2">score {fixed(i.final_score, 0)}</span>
                    </div>
                    {i.switch_to && (
                      <p className="text-[0.85rem]">
                        Switch to <span className="font-semibold">{fundName(i.switch_to)}</span>
                      </p>
                    )}
                    {i.constraints_triggered.length > 0 && (
                      <ul className="flex flex-wrap gap-1.5">
                        {i.constraints_triggered.map((c) => (
                          <li key={c} className="inline-flex items-center gap-1 rounded-[2px] border border-alert px-1.5 py-px text-[0.75rem] font-semibold text-alert">
                            <IconAlert className="size-3" /> {ruleLabel(c)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <dl className="grid grid-cols-[9.5rem_1fr] items-center gap-x-3 gap-y-1.5 text-[0.85rem]">
                    {COMPONENTS.map(([k, label]) => (
                      <div key={k} className="contents">
                        <dt className="text-ink-2">
                          {label}
                          {r.weights[k] === 0 && <span className="block text-[0.75rem] text-ink-3">not weighted</span>}
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
                  <ul className="space-y-1 text-[0.9rem] text-ink">
                    {i.reasons.map((x) => (
                      <li key={x} className="flex gap-2">
                        <span aria-hidden className="mt-[0.6em] size-1 shrink-0 rounded-full bg-ink-3" />
                        {x}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </Figure>
        </div>
      )}
    </Status>
  )
}
