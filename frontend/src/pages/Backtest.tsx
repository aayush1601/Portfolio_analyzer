import { useEffect, useState } from 'react'
import { useApi } from '../api'
import { fixed, pct, signed } from '../format'
import { Button, Card, Chip, IconRefresh, Status } from '../ui'

type Metrics = { cagr: number; volatility: number; sharpe: number; sortino: number; max_drawdown: number; calmar: number; cvar_95: number; turnover: number }
type Test = { strategy: string; versus: string; question: string; sharpe_diff: number; p_value: number; ci_low: number; ci_high: number }
type Run = {
  run_id: string
  status: 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED'
  error?: string
  created_at: string
  data_fingerprint: string
  config: { cost_bps: number; lookback_days: number; bootstrap: { resamples: number; block_days: number } }
  period: { start: string; end: string; rebalances: number }
  metrics: Record<string, Metrics>
  tests: Test[]
  regimes: ({ dimension: string; regime: string; days: number } & Record<string, number | string>)[]
  news_coverage: { rebalances_with_news: number; rebalances: number }
  equity: { dates: string[] } & Record<string, number[] | string[]>
}

const SERIES: { key: string; label: string; color: string; dash?: string; width: number }[] = [
  { key: 'D_news_aware_mv', label: 'D · + News', color: 'var(--color-brand)', width: 2.6 },
  { key: 'C_mean_variance', label: 'C · + Returns', color: 'var(--color-accent)', width: 2, dash: '6 4' },
  { key: 'B_min_variance', label: 'B · + Risk', color: 'var(--color-via)', width: 2 },
  { key: 'A_equal_weight', label: 'A · Equal weight', color: 'var(--color-ink-3)', width: 1.6 },
  { key: 'buy_and_hold', label: 'Buy and hold', color: 'var(--color-ink-2)', width: 1.6, dash: '2 3' },
  { key: 'benchmark', label: 'NIFTY 50', color: 'var(--color-ink)', width: 1.6, dash: '8 3 2 3' },
]
const NAME = Object.fromEntries(SERIES.map((s) => [s.key, s.label]))

function EquityChart({ run }: { run: Run }) {
  const series = SERIES.filter((s) => Array.isArray(run.equity[s.key]))
  const all = series.flatMap((s) => run.equity[s.key] as number[])
  const lo = Math.min(...all, 1), hi = Math.max(...all)
  const n = run.equity.dates.length
  const W = 1000, H = 300
  const x = (i: number) => (i / (n - 1)) * W
  const y = (v: number) => H - ((Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))) * H
  const end = series.map((s) => ({ ...s, v: (run.equity[s.key] as number[])[n - 1] })).sort((a, b) => b.v - a.v)
  return (
    <figure>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative h-56 sm:h-72 sm:flex-1">
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" aria-hidden>
            <line x1={0} x2={W} y1={y(1)} y2={y(1)} stroke="var(--color-line)" vectorEffect="non-scaling-stroke" />
            {series.map((s) => (
              <path
                key={s.key}
                d={(run.equity[s.key] as number[]).map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')}
                fill="none"
                stroke={s.color}
                strokeWidth={s.width}
                strokeDasharray={s.dash}
                vectorEffect="non-scaling-stroke"
                strokeLinejoin="round"
              />
            ))}
          </svg>
          <span className="absolute right-0 -translate-y-full text-[0.72rem] text-ink-3" style={{ top: `${(y(1) / H) * 100}%` }}>
            ₹1 start
          </span>
        </div>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[0.8rem] sm:block sm:w-40 sm:shrink-0 sm:space-y-1.5" aria-label="Growth of ₹1 by strategy">
          {end.map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              <svg width="22" height="8" aria-hidden className="shrink-0">
                <line x1="0" x2="22" y1="4" y2="4" stroke={s.color} strokeWidth={s.width + 0.4} strokeDasharray={s.dash} />
              </svg>
              <span className="min-w-0 flex-1 truncate text-ink-2">{s.label}</span>
              <span className="num font-bold">₹{s.v.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-2 flex justify-between gap-2 text-[0.75rem] text-ink-3 sm:pr-[10.75rem]">
        <span>{run.equity.dates[0]}</span>
        <span>Log scale · growth of ₹1, after costs</span>
        <span>{run.equity.dates[n - 1]}</span>
      </figcaption>
    </figure>
  )
}

function verdict(t: Test) {
  if (t.p_value < 0.05) return <Chip tone="gain">Significant (p {fixed(t.p_value, 3)})</Chip>
  return <Chip>Not significant (p {fixed(t.p_value, 2)})</Chip>
}

function headline(r: Run) {
  const steps = r.tests.filter((t) => ['A_equal_weight', 'B_min_variance', 'C_mean_variance'].includes(t.versus) && t.strategy !== 'benchmark')
  const sig = steps.filter((t) => t.p_value < 0.05).length
  const best = Object.entries(r.metrics).filter(([k]) => k !== 'benchmark').sort((a, b) => b[1].sharpe - a[1].sharpe)[0]
  return sig
    ? `${sig} of ${steps.length} layers add a statistically significant edge; best Sharpe: ${NAME[best[0]]} at ${fixed(best[1].sharpe)}.`
    : `Since ${r.period.start.slice(0, 4)}, no layer adds a statistically significant edge over the one before it.`
}

function Results({ r }: { r: Run }) {
  const keys = SERIES.map((s) => s.key).filter((k) => r.metrics[k])
  const nc = r.news_coverage
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <Card
        title={headline(r)}
        dek={`Monthly rebalancing from ${r.period.start} to ${r.period.end} (${r.period.rebalances} rebalances) over the 50 NIFTY stocks and 15 research funds, ${r.config.cost_bps} bps cost on every rupee traded, estimates strictly from data available at each rebalance.`}
        source={`Run ${r.run_id} · data fingerprint ${r.data_fingerprint}. All strategies use today’s NIFTY 50 constituents, so every line, the benchmark aside, is flattered by survivorship bias. Research output, not financial advice.`}
      >
        <EquityChart run={r} />
      </Card>

      <Card title="Performance after costs" dek="A → D adds one layer at a time: risk, then return estimates, then news.">
        <div className="-mx-5 overflow-x-auto sm:-mx-6">
          <table className="w-full min-w-[760px] text-[0.88rem]">
            <thead>
              <tr className="border-b border-line text-left text-[0.78rem] text-ink-3">
                {['Strategy', 'CAGR', 'Volatility', 'Sharpe', 'Sortino', 'Worst fall', 'Calmar', 'Bad day (CVaR)', 'Traded / yr'].map((h, i) => (
                  <th key={h} scope="col" className={`px-3 py-2.5 font-bold first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6 ${i ? 'text-right' : ''}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => {
                const m = r.metrics[k]
                return (
                  <tr key={k} className="border-b border-line-soft last:border-b-0">
                    <th scope="row" className="py-2.5 pr-3 pl-5 text-left font-bold sm:pl-6">{NAME[k]}</th>
                    <td className="num px-3 text-right">{pct(m.cagr)}</td>
                    <td className="num px-3 text-right">{pct(m.volatility)}</td>
                    <td className="num px-3 text-right font-bold">{fixed(m.sharpe)}</td>
                    <td className="num px-3 text-right">{fixed(m.sortino)}</td>
                    <td className="num px-3 text-right text-loss">{pct(m.max_drawdown)}</td>
                    <td className="num px-3 text-right">{fixed(m.calmar)}</td>
                    <td className="num px-3 text-right">{pct(m.cvar_95, 2)}</td>
                    <td className="num py-2.5 pr-5 pl-3 text-right sm:pr-6">{k === 'benchmark' ? '–' : `${fixed(m.turnover, 1)}×`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
        <Card
          title="Is each difference real?"
          dek={`Stationary block bootstrap (${r.config.bootstrap.resamples} resamples, ${r.config.bootstrap.block_days}-day blocks) of the Sharpe-ratio difference; one-sided, p < 0.05 counts as significant.`}
        >
          <ul className="-mx-5 divide-y divide-line-soft border-t border-line sm:-mx-6">
            {r.tests.map((t) => (
              <li key={t.strategy + t.versus} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3 sm:px-6">
                <div className="min-w-0">
                  <p className="font-bold text-ink">
                    {NAME[t.strategy]} vs {NAME[t.versus]}
                  </p>
                  <p className="text-[0.8rem] text-ink-3">
                    {t.question} · Sharpe {signed(t.sharpe_diff)} (95%: {signed(t.ci_low)} to {signed(t.ci_high)})
                  </p>
                </div>
                {verdict(t)}
              </li>
            ))}
          </ul>
        </Card>
        <Card
          title={`The news layer acted on ${nc.rebalances_with_news} of ${nc.rebalances} rebalances.`}
          dek="So D is almost exactly C, and this run cannot answer whether news helps (RQ3). It becomes answerable once historical news is backfilled or enough collected news accumulates; the strategy, costs and tests are already in place."
        >
          <div className="h-2 rounded-full bg-line-soft" role="img" aria-label={`${nc.rebalances_with_news} of ${nc.rebalances} rebalances had news`}>
            <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(1, (nc.rebalances_with_news / nc.rebalances) * 100)}%` }} />
          </div>
        </Card>
      </div>

      <Card title="Sharpe ratio by market regime" dek="Days labelled by the regime known the day before: the NIFTY 50’s 6-month trend, and India VIX above or below its median.">
        <div className="-mx-5 overflow-x-auto sm:-mx-6">
          <table className="w-full min-w-[760px] text-[0.88rem]">
            <thead>
              <tr className="border-b border-line text-left text-[0.78rem] text-ink-3">
                <th scope="col" className="py-2.5 pr-3 pl-5 font-bold sm:pl-6">Regime</th>
                <th scope="col" className="px-3 text-right font-bold">Days</th>
                {keys.map((k) => (
                  <th key={k} scope="col" className="px-3 text-right font-bold last:pr-5 sm:last:pr-6">{NAME[k]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.regimes.map((g) => (
                <tr key={g.regime} className="border-b border-line-soft last:border-b-0">
                  <th scope="row" className="py-2.5 pr-3 pl-5 text-left font-bold sm:pl-6">{g.regime}</th>
                  <td className="num px-3 text-right text-ink-2">{g.days}</td>
                  {keys.map((k) => (
                    <td key={k} className={`num px-3 text-right last:pr-5 sm:last:pr-6 ${(g[k] as number) < 0 ? 'text-loss' : ''}`}>{fixed(g[k] as number)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

export function BacktestPage() {
  const list = useApi<{ run_id: string; status: string }[]>('/backtest')
  const [runId, setRunId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const latest = list.data?.find((r) => r.status === 'DONE')?.run_id ?? null
  const pending = list.data?.find((r) => r.status === 'QUEUED' || r.status === 'RUNNING')
  const id = runId ?? latest
  const q = useApi<Run>(id ? `/backtest/${id}` : null)
  const { reload } = list

  useEffect(() => {
    if (!pending) return
    const t = window.setTimeout(reload, 3000)
    return () => window.clearTimeout(t)
  }, [pending, list.data, reload])

  async function runAgain() {
    setStarting(true)
    try {
      await fetch('/api/backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      setRunId(null)
      reload()
    } finally {
      setStarting(false)
    }
  }

  const bar = (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <p className="text-[0.88rem] text-ink-2">
        {pending ? 'A new run is in progress (about a minute)…' : id ? `Showing run ${id}.` : 'No backtest has been run yet.'}
      </p>
      <Button onClick={runAgain} disabled={starting || Boolean(pending)}>
        <IconRefresh /> {pending ? 'Running…' : 'Run again'}
      </Button>
    </div>
  )

  if (!id) return <>{bar}{list.error && <Status q={list} what="backtest runs">{() => null}</Status>}</>
  return (
    <>
      {bar}
      <Status q={q} what="the backtest">{(r) => <Results r={r} />}</Status>
    </>
  )
}
