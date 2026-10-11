import { useEffect, useState } from 'react'
import { Riskometer, TailHistogram } from '../charts'
import { api, useApi, type HoldingPeriod, type Reference, type Risk, type StressResult } from '../api'
import { Button, Card, IconPlus, IconTrash, Notes, Plate, Segmented, Status } from '../ui'
import { fixed, inr, pct, signedInr, signedPct } from '../format'

const LOOKBACKS = [
  { days: 63, label: '3 months' },
  { days: 252, label: '1 year' },
  { days: 756, label: '3 years' },
  { days: 1260, label: '5 years' },
]
const SHORT: Record<number, string> = { 63: '3M', 252: '1Y', 756: '3Y', 1260: '5Y' }
const describe = (rows: { sector: string; shock: string }[]) =>
  rows.map((r) => `${r.sector} ${Number(r.shock) < 0 ? 'falls' : 'rises'} ${Math.abs(Number(r.shock))}%`).join(' and ')
const field =
  'rounded-lg border border-line bg-panel px-3 py-2 text-[0.9rem] font-medium text-ink hover:border-ink-3 focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40'

function Metric({ label, value, help }: { label: string; value: string; help: string }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-x-4 border-b border-line-soft py-2">
      <dt className="font-semibold text-ink">{label}</dt>
      <dd className="num row-span-2 self-center text-right text-[1.05rem] font-bold">{value}</dd>
      <dd className="text-[0.85rem] text-ink-2">{help}</dd>
    </div>
  )
}

function Stress({ pid, reference }: { pid: string; reference: Reference }) {
  const sectors = [...new Set(reference.stocks.map((s) => s.sector))].sort()
  const [rows, setRows] = useState([{ sector: 'Information Technology', shock: '-10' }])
  // The scenario travels with its result, so editing the form never relabels an old answer.
  const [ran, setRan] = useState<{ result: StressResult; scenario: string } | null>(null)
  const result = ran?.result
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Open on a finding rather than an empty panel: run the default scenario once.
  useEffect(() => {
    let live = true
    api<StressResult>(`/portfolio/${pid}/stress`, { method: 'POST', body: JSON.stringify({ shocks: { 'Information Technology': -0.1 } }) })
      .then((r) => live && setRan({ result: r, scenario: describe([{ sector: 'Information Technology', shock: '-10' }]) }))
      .catch(() => {})
    return () => {
      live = false
    }
  }, [pid])

  async function run(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (rows.some((r) => r.shock.trim() === '' || Number.isNaN(Number(r.shock)))) return setError('Each shock must be a number, e.g. −10 for a 10% fall.')
    if (new Set(rows.map((r) => r.sector)).size < rows.length) return setError('Each sector can appear once. Remove the repeat or pick another sector.')
    const shocks = Object.fromEntries(rows.map((r) => [r.sector, Number(r.shock) / 100]))
    setBusy(true)
    try {
      setRan({ result: await api<StressResult>(`/portfolio/${pid}/stress`, { method: 'POST', body: JSON.stringify({ shocks }) }), scenario: describe(rows) })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title={
        ran
          ? `If ${ran.scenario}, what’s visible of this portfolio would move about ${signedPct(ran.result.estimated_loss)} (${inr(ran.result.estimated_loss_inr)}).`
          : 'What a sector shock would do to this portfolio'
      }
      dek={
        result && result.unshocked_unmapped > 0.0005
          ? `Not counted: ${pct(result.unshocked_unmapped)} of the portfolio sits in funds whose holdings aren’t loaded yet, so their share of this shock is unknown. A linear, one-step estimate, not a forecast.`
          : 'Shocks hit effective (look-through) sector exposure, so a fall in IT reaches you through your funds too. A linear, one-step estimate, not a forecast.'
      }
    >
      <form onSubmit={run} className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select aria-label={`Shock ${i + 1} sector`} className={`${field} min-w-0 flex-1`} value={r.sector} onChange={(e) => setRows((x) => x.map((y, j) => (j === i ? { ...y, sector: e.target.value } : y)))}>
              {sectors.map((s) => <option key={s}>{s}</option>)}
            </select>
            <label className="flex items-center gap-1">
              <input aria-label={`Shock ${i + 1} percent`} inputMode="decimal" className={`${field} num w-20 text-right`} value={r.shock} onChange={(e) => setRows((x) => x.map((y, j) => (j === i ? { ...y, shock: e.target.value } : y)))} />
              <span className="text-ink-2">%</span>
            </label>
            <button type="button" aria-label={`Remove shock ${i + 1}`} className="grid size-9 place-items-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-40 disabled:hover:bg-transparent" disabled={rows.length === 1} onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>
              <IconTrash />
            </button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="button" onClick={() => setRows((x) => [...x, { sector: sectors.find((s) => !x.some((y) => y.sector === s)) ?? sectors[0], shock: '-10' }])}>
            <IconPlus /> Add sector
          </Button>
          <Button variant="primary" type="submit" disabled={busy}>{busy ? 'Running…' : 'Run stress test'}</Button>
        </div>
        {error && <p role="alert" className="text-loss">{error}</p>}
      </form>
      {result && result.top_contributors.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 text-[0.85rem] font-bold text-ink-2">Where the move comes from</h3>
          <ul className="space-y-1">
            {result.top_contributors.map((c) => (
              <li key={c.symbol} className="flex items-baseline justify-between gap-3 border-b border-line-soft py-1">
                {c.symbol === 'Other/Unmapped' ? <span className="text-ink-2 italic">Inside funds, not yet visible</span> : <Plate id={c.symbol} />}
                <span className="num">{signedPct(c.loss, 2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}

function holdingHeadline(h: HoldingPeriod[]) {
  const first = h[0], last = h[h.length - 1]
  if (!first || !last) return 'How holding longer changes the odds'
  return last.prob_loss < first.prob_loss
    ? `The longer you hold, the less likely a loss: ${pct(first.prob_loss, 0)} over ${first.label}, ${pct(last.prob_loss, 0)} over ${last.label}.`
    : `This mix has averaged a negative return, so holding longer makes a loss more likely: ${pct(first.prob_loss, 0)} over ${first.label}, ${pct(last.prob_loss, 0)} over ${last.label}.`
}

/** Time diversification, both halves: the chance of a loss vs how wide the outcomes spread. */
function Holding({ r }: { r: Risk }) {
  const years = Math.round(r.holding_history_days / 252)
  return (
    <Card
      title={holdingHeadline(r.holding_periods)}
      dek={`But the range of outcomes widens the longer you hold. Estimated from the last ${years} years of today’s mix, which averaged ${signedPct(r.holding_mean_return_ann)} a year; if the future is weaker, these chances of a loss are too optimistic.`}
      source="Estimate: daily log returns assumed independent and normal. “Actually happened” counts every past window of that length; they overlap, so long horizons rest on few truly independent periods."
    >
      <ul className="space-y-3">
        {r.holding_periods.map((h) => (
          <li key={h.label} className="grid grid-cols-[8.5rem_minmax(0,1fr)] items-center gap-4 rounded-xl border border-line p-4">
            <div>
              <p className="text-[0.82rem] font-bold text-ink-2">Held for {h.label}</p>
              <p className="num text-[1.6rem] leading-tight font-extrabold">{pct(h.prob_loss, 0)}</p>
              <p className="text-[0.78rem] text-ink-2">chance of ending down</p>
              <div className="mt-1.5 h-1.5 rounded-full bg-line-soft" role="img" aria-label={`${pct(h.prob_loss, 0)} chance of a loss`}>
                <div className="h-full rounded-full bg-loss" style={{ width: `${h.prob_loss * 100}%` }} />
              </div>
            </div>
            <dl className="space-y-1.5 text-[0.85rem]">
              <div className="flex flex-wrap justify-between gap-x-3">
                <dt className="text-ink-3">Typical outcome</dt>
                <dd className="num font-bold whitespace-nowrap">{signedPct(h.median_return)}</dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-3">
                <dt className="text-ink-3">Bad case (1 in 20)</dt>
                <dd className={`num font-bold whitespace-nowrap ${h.bad_return < 0 ? 'text-loss' : ''}`}>
                  {signedPct(h.bad_return)} <span className="font-medium text-ink-2">({signedInr(h.bad_inr)})</span>
                </dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-3 border-t border-line-soft pt-1.5">
                <dt className="text-ink-3">Actually happened</dt>
                <dd className="num whitespace-nowrap">{h.observed_prob_loss === null ? 'not enough history' : `${pct(h.observed_prob_loss, 0)} ended down`}</dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function RiskPage({ pid, reference }: { pid: string; reference: Reference }) {
  const [lookback, setLookback] = useState(252)
  const [confidence, setConfidence] = useState(0.95)
  const q = useApi<Risk>(`/portfolio/${pid}/risk?lookback_days=${lookback}&confidence=${confidence}`)
  const odds = Math.round(1 / (1 - confidence))
  const span = LOOKBACKS.find((l) => l.days === lookback)!.label

  const controls = (
    <div className="no-print flex flex-wrap gap-2">
      <Segmented label="History window" options={LOOKBACKS.map((l) => ({ value: l.days, label: SHORT[l.days] }))} value={lookback} onChange={setLookback} />
      <Segmented label="Confidence" options={[0.9, 0.95, 0.99].map((c) => ({ value: c, label: pct(c, 0) }))} value={confidence} onChange={setConfidence} />
    </div>
  )

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:items-start">
      <Status q={q} what="risk metrics">
        {(r) => (
          <Card
            title={`Risk score ${r.risk_score} of 100, ${r.risk_band.toLowerCase()}. On a bad day (1\u00a0in\u00a0${odds}) this portfolio loses about ${pct(r.var_1d.historical)} or more.`}
            dek={`Today’s weights applied to the last ${r.observations} trading days (${span}). Cash counts as risk-free.`}
            aside={controls}
            source={
              <>
                Score weights {r.score_weights_version}, volatility annualised over 252 days, beta vs NIFTY 50.
                {r.notes.length > 0 && <span className="mt-1 block"><Notes notes={r.notes} /></span>}
              </>
            }
          >
            <div className="grid items-center gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
              <div className="text-center">
                <Riskometer score={r.risk_score} band={r.risk_band} />
                <p className="mt-1 text-[0.85rem] font-bold text-ink-2">{r.risk_band} risk · score {r.risk_score} of 100</p>
              </div>
              <div>
                <TailHistogram edges={r.return_histogram.edges} counts={r.return_histogram.counts} varLoss={r.var_1d.historical} odds={odds} />
                <p className="mt-1 text-[0.8rem] text-ink-3">Each bar counts the days with that return; hatched bars are the bad-day tail.</p>
              </div>
            </div>
            <div className="mt-8 grid gap-x-8 md:grid-cols-2">
              <div>
                <h3 className="border-b border-line pb-2 text-[1rem] font-extrabold text-ink">Return and swings</h3>
                <dl>
                <Metric label="Annual return" value={signedPct(r.return_ann)} help="Average daily return × 252." />
                <Metric label="Volatility" value={pct(r.volatility_ann)} help="How much the value swings in a typical year." />
                <Metric label="Sharpe ratio" value={fixed(r.sharpe)} help={`Return above the ${pct(r.risk_free_rate)} risk-free rate per unit of volatility.`} />
                <Metric label="Sortino ratio" value={fixed(r.sortino)} help="Like Sharpe, but only counts downside swings." />
                </dl>
                <h3 className="mt-6 border-b border-line pb-2 text-[1rem] font-extrabold text-ink">Market and concentration</h3>
                <dl>
                <Metric label="Beta" value={fixed(r.beta)} help="Moves this much for every 1% the NIFTY 50 moves." />
                <Metric label="Average correlation" value={r.avg_correlation === null ? 'n/a' : fixed(r.avg_correlation)} help="How alike your holdings move (1 = identical)." />
                <Metric label="Concentration (direct)" value={fixed(r.hhi_direct, 3)} help="HHI of what you hold directly: 1/N for N equal holdings." />
                {r.hhi_effective !== null && <Metric label="Concentration (look-through)" value={fixed(r.hhi_effective, 3)} help="HHI once funds are opened up." />}
                <Metric label="Diversification" value={`${r.diversification_score}/100`} help={`Diversification ratio ${fixed(r.diversification_ratio)}: how much mixing holdings cancels swings.`} />
                </dl>
              </div>
              <div className="mt-6 md:mt-0">
                <h3 className="border-b border-line pb-2 text-[1rem] font-extrabold text-ink">Losses</h3>
                <dl>
                <Metric
                  label="Worst fall"
                  value={pct(r.max_drawdown)}
                  help={`Largest peak-to-trough drop in the chosen window. The risk score always uses the worst fall over the last ${Math.round(r.score_drawdown_days / 252)} years: ${pct(r.score_drawdown)}.`}
                />
                <Metric label="1-day VaR, historical" value={pct(r.var_1d.historical)} help={`Loss exceeded on 1 day in ${odds}, read from past days.`} />
                <Metric label="1-day VaR, parametric" value={pct(r.var_1d.parametric)} help="Same, assuming returns are normally distributed." />
                <Metric label="1-day VaR, Monte Carlo" value={pct(r.var_1d.monte_carlo)} help="Same, from 10,000 simulated days (seeded)." />
                <Metric label="Expected shortfall (CVaR)" value={pct(r.cvar_1d)} help={`Average loss on those 1-in-${odds} bad days.`} />
                </dl>
              </div>
            </div>
          </Card>
        )}
      </Status>
      <div className="grid gap-5">
        {q.data && <Holding r={q.data} />}
        <Stress pid={pid} reference={reference} />
      </div>
    </div>
  )
}
