// Typed client for the FastAPI backend (docs/api/openapi.yaml). Vite proxies /api to it in dev.
import { useCallback, useEffect, useState } from 'react'

export type AssetType = 'STOCK' | 'MF' | 'CASH'

export type Holding = { asset_type: AssetType; asset_id: string; quantity: number; avg_cost: number }
export type HoldingValue = Holding & {
  price: number
  price_date: string | null
  value: number
  weight: number
  pl: number
  daily_pl: number
}
export type PortfolioSummary = { portfolio_id: string; name: string; created_at: string }
export type Snapshot = {
  portfolio_id: string
  as_of: string
  total_value: number
  daily_pl: number
  total_pl: number
  holdings: HoldingValue[]
}

export type Company = {
  symbol: string
  sector: string
  direct: number
  indirect: number
  effective: number
  via: { fund: string; contribution: number }[]
}
export type Exposure = {
  portfolio_id: string
  as_of: string
  holdings_as_of: Record<string, string>
  companies: Company[]
  sectors: { sector: string; direct: number; effective: number }[]
  overlap: { fund_a: string; fund_b: string; overlap: number }[]
  unmapped: number
  hhi_effective: number
  n_effective: number | null
  notes: string[]
}

export type Risk = {
  as_of: string
  lookback_days: number
  observations: number
  confidence: number
  risk_free_rate: number
  return_ann: number
  volatility_ann: number
  sharpe: number
  sortino: number
  max_drawdown: number
  var_1d: { historical: number; parametric: number; monte_carlo: number }
  cvar_1d: number
  beta: number
  avg_correlation: number | null
  hhi_direct: number
  hhi_effective: number | null
  diversification_ratio: number
  diversification_score: number
  risk_score: number
  risk_band: string
  score_weights_version: string
  return_histogram: { edges: number[]; counts: number[] }
  notes: string[]
}

export type StressResult = {
  scenario: string
  estimated_loss: number
  estimated_loss_inr: number
  top_contributors: { symbol: string; loss: number }[]
  unshocked_unmapped: number
}

export type NewsItem = {
  news_id: string
  headline: string
  source: string
  url: string
  published_at: string
  symbols: string[]
  sectors: string[]
  sentiment: { label: string; score: number; confidence: number }
  importance: number
  reliability: number
  recency: number
  matched_via: 'company' | 'sector'
  effective_exposure: number
  impact: number
}
export type PortfolioNews = {
  as_of: string
  lookback_hours: number
  portfolio_news_impact: number
  alert: boolean
  alert_threshold: number
  items: NewsItem[]
  notes: string[]
}

export type Recommendation = {
  asset_id: string
  asset_type: AssetType
  action: string
  final_score: number
  components: Record<string, number | null>
  reasons: string[]
  constraints_triggered: string[]
  switch_to: string | null
  blocked_action: string | null
}
export type Recommendations = {
  as_of: string
  disclaimer: string
  config_version: string
  items: Recommendation[]
  notes: string[]
}

export type Reference = {
  stocks: { symbol: string; name: string; sector: string }[]
  funds: { scheme_code: string; name: string; amc: string; category: string }[]
  caps: { company: number; sector: number }
}

export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!r.ok) {
    const body = await r.json().catch(() => null)
    const detail = body?.detail
    throw new ApiError(
      typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : `HTTP ${r.status}`,
    )
  }
  return r.json()
}

export type Loadable<T> = { data: T | null; error: string | null; loading: boolean; reload: () => void }

/** GET `path` (skipped while null); refetches when the path changes or reload() is called. */
export function useApi<T>(path: string | null): Loadable<T> {
  const [tick, setTick] = useState(0)
  const key = path === null ? null : `${path}#${tick}`
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null }>({
    key: null,
    data: null,
    error: null,
  })
  useEffect(() => {
    if (key === null || path === null) return
    let live = true
    api<T>(path)
      .then((data) => live && setState({ key, data, error: null }))
      .catch((e: Error) => live && setState({ key, data: null, error: e.message }))
    return () => {
      live = false
    }
  }, [key, path])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  const settled = state.key === key
  // Keep showing the previous data while a refetch is in flight, so tables don't flash empty.
  return { data: state.data, error: settled ? state.error : null, loading: key !== null && !settled, reload }
}
