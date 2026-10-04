import { useEffect, useState } from 'react'
import { TailHistogram } from '../charts'
import { api, useApi, type Reference, type Risk, type StressResult } from '../api'
import { Button, Figure, IconPlus, IconTrash, Notes, Plate, Status } from '../ui'
import { fixed, inr, pct, signedPct } from '../format'

const LOOKBACKS = [
  { days: 63, label: '3 months' },
  { days: 252, label: '1 year' },
  { days: 756, label: '3 years' },
  { days: 1260, label: '5 years' },
]
const field =
  'rounded-[3px] border border-rule bg-panel px-2 py-1.5 text-[0.9rem] text-ink hover:border-ink-3 focus:border-direct focus:outline-none'

function Metric({ label, value, help }: { label: string; value: string; help: string }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-x-4 border-b border-rule-soft py-2">
      <dt className="font-semibold text-ink">{label}</dt>
      <dd className="num row-span-2 self-center text-right text-[1.05rem]">{value}</dd>
      <dd className="text-[0.85rem] text-ink-2">{help}</dd>
    </div>
  )
}

function ScoreScale({ score, band }: { score: number; band: string }) {
  const bands = [
    { name: 'Low', to: 33 },
    { name: 'Moderate', to: 66 },
    { name: 'High', to: 100 },
  ]
  return (
    <div aria-label={`Risk score ${score} of 100, ${band}`} role="img">
      <div className="relative flex h-3">
        {bands.map((b, i) => (
          <div
            key={b.name}
            className={`h-full border-r border-panel ${['bg-direct-soft', 'bg-[#a9bfd6]', 'bg-direct'][i]}`}
            style={{ width: `${b.to - (bands[i - 1]?.to ?? 0)}%` }}
          />
        ))}
        <div className="absolute -top-1.5 h-6 w-1 -translate-x-1/2 bg-ink ring-2 ring-panel" style={{ left: `${score}%` }} />
      </div>
      <div className="mt-1 flex text-[0.75rem] text-ink-3">
        {bands.map((b, i) => (
          <span key={b.name} style={{ width: `${b.to - (bands[i - 1]?.to ?? 0)}%` }}>
            {b.name}
          </span>
        ))}
      </div>
    </div>
  )
}

function Stress({ pid, reference }: { pid: string; reference: Reference }) {
  const sectors = [...new Set(reference.stocks.map((s) => s.sector))].sort()
  const [rows, setRows] = useState([{ sector: 'Information Technology', shock: '-10' }])
  const [result, setResult] = useState<StressResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Open on a finding rather than an empty panel: run the default scenario once.
  useEffect(() => {
    let live = true
    api<StressResult>(`/portfolio/${pid}/stress`, { method: 'POST', body: JSON.stringify({ shocks: { 'Information Technology': -0.1 } }) })
      .then((r) => live && setResult(r))
      .catch(() => {})
    return () => {
      live = false
    }
  }, [pid])

  async function run(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const shocks = Object.fromEntries(rows.map((r) => [r.sector, Number(r.shock) / 100]))
    if (Object.values(shocks).some((v) => Number.isNaN(v))) return setError('Each shock must be a number, e.g. −10 for a 10% fall.')
    setBusy(true)
    try {
      setResult(await api<StressResult>(`/portfolio/${pid}/stress`, { method: 'POST', body: JSON.stringify({ shocks }) }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const scenario = rows.map((r) => `${r.sector} ${Number(r.shock) > 0 ? '+' : ''}${r.shock}%`).join(', ')
  return (
    <Figure
      title={
        result
          ? `If ${scenario}, this portfolio would move about ${signedPct(result.estimated_loss)}: ${inr(result.estimated_loss_inr)}.`
          : 'What a sector shock would do to this portfolio'
      }
      dek="Shocks hit effective (look-through) sector exposure, so a fall in IT reaches you through your funds too. A linear, one-step estimate, not a forecast."
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
            <button type="button" aria-label={`Remove shock ${i + 1}`} className="p-1 text-ink-3 hover:text-ink disabled:opacity-40" disabled={rows.length === 1} onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>
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
        {error && <p role="alert" className="text-alert">{error}</p>}
      </form>
      {result && result.top_contributors.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 text-[0.85rem] font-semibold text-ink-2">Where the move comes from</h3>
          <ul className="space-y-1">
            {result.top_contributors.map((c) => (
              <li key={c.symbol} className="flex items-baseline justify-between gap-3 border-b border-rule-soft py-1">
                {c.symbol === 'Other/Unmapped' ? <span className="text-ink-2 italic">Inside funds, not yet visible</span> : <Plate id={c.symbol} />}
                <span className="num">{signedPct(c.loss, 2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Figure>
  )
}

export function RiskPage({ pid, reference }: { pid: string; reference: Reference }) {
  const [lookback, setLookback] = useState(252)
  const [confidence, setConfidence] = useState(0.95)
  const q = useApi<Risk>(`/portfolio/${pid}/risk?lookback_days=${lookback}&confidence=${confidence}`)
  const odds = Math.round(1 / (1 - confidence))
  const window = LOOKBACKS.find((l) => l.days === lookback)!.label

  const controls = (
    <div className="no-print flex flex-wrap gap-2">
      <label className="text-[0.85rem] text-ink-2">
        <span className="sr-only">History window</span>
        <select className={field} value={lookback} onChange={(e) => setLookback(Number(e.target.value))}>
          {LOOKBACKS.map((l) => <option key={l.days} value={l.days}>Last {l.label}</option>)}
        </select>
      </label>
      <label className="text-[0.85rem] text-ink-2">
        <span className="sr-only">Confidence</span>
        <select className={field} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}>
          {[0.9, 0.95, 0.99].map((c) => <option key={c} value={c}>{pct(c, 0)} confidence</option>)}
        </select>
      </label>
    </div>
  )

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
      <Status q={q} what="risk metrics">
        {(r) => (
          <Figure
            title={`Risk score ${r.risk_score} of 100, ${r.risk_band.toLowerCase()}. On a bad day (1 in ${odds}) this portfolio loses about ${pct(r.var_1d.historical)} or more.`}
            dek={`Today’s weights applied to the last ${r.observations} trading days (${window}). Cash counts as risk-free.`}
            aside={controls}
            source={
              <>
                Score weights {r.score_weights_version} (config/risk_score.yaml), volatility annualised over 252 days, beta vs NIFTY 50.
                {r.notes.length > 0 && <span className="mt-1 block"><Notes notes={r.notes} /></span>}
              </>
            }
          >
            <TailHistogram edges={r.return_histogram.edges} counts={r.return_histogram.counts} varLoss={r.var_1d.historical} odds={odds} />
            <p className="mt-1 mb-5 text-[0.8rem] text-ink-3">Each bar counts the days with that return; hatched bars are the bad-day tail.</p>
            <ScoreScale score={r.risk_score} band={r.risk_band} />
            <dl className="mt-5 grid gap-x-8 md:grid-cols-2">
              <div>
                <h3 className="border-b border-ink pb-1 text-[0.8rem] font-semibold text-ink-2">Return and swings</h3>
                <Metric label="Annual return" value={signedPct(r.return_ann)} help="Average daily return × 252." />
                <Metric label="Volatility" value={pct(r.volatility_ann)} help="How much the value swings in a typical year." />
                <Metric label="Sharpe ratio" value={fixed(r.sharpe)} help={`Return above the ${pct(r.risk_free_rate)} risk-free rate per unit of volatility.`} />
                <Metric label="Sortino ratio" value={fixed(r.sortino)} help="Like Sharpe, but only counts downside swings." />
                <h3 className="mt-4 border-b border-ink pb-1 text-[0.8rem] font-semibold text-ink-2">Market and concentration</h3>
                <Metric label="Beta" value={fixed(r.beta)} help="Moves this much for every 1% the NIFTY 50 moves." />
                <Metric label="Average correlation" value={r.avg_correlation === null ? 'n/a' : fixed(r.avg_correlation)} help="How alike your holdings move (1 = identical)." />
                <Metric label="Concentration (direct)" value={fixed(r.hhi_direct, 3)} help="HHI of what you hold directly: 1/N for N equal holdings." />
                {r.hhi_effective !== null && <Metric label="Concentration (look-through)" value={fixed(r.hhi_effective, 3)} help="HHI once funds are opened up." />}
                <Metric label="Diversification" value={`${r.diversification_score}/100`} help={`Diversification ratio ${fixed(r.diversification_ratio)}: how much mixing holdings cancels swings.`} />
              </div>
              <div>
                <h3 className="border-b border-ink pb-1 text-[0.8rem] font-semibold text-ink-2">Losses</h3>
                <Metric label="Worst fall" value={pct(r.max_drawdown)} help="Largest peak-to-trough drop in the window." />
                <Metric label="1-day VaR, historical" value={pct(r.var_1d.historical)} help={`Loss exceeded on 1 day in ${odds}, read from past days.`} />
                <Metric label="1-day VaR, parametric" value={pct(r.var_1d.parametric)} help="Same, assuming returns are normally distributed." />
                <Metric label="1-day VaR, Monte Carlo" value={pct(r.var_1d.monte_carlo)} help="Same, from 10,000 simulated days (seeded)." />
                <Metric label="Expected shortfall (CVaR)" value={pct(r.cvar_1d)} help="Average loss on those 1-in-N bad days." />
              </div>
            </dl>
          </Figure>
        )}
      </Status>
      <Stress pid={pid} reference={reference} />
    </div>
  )
}
