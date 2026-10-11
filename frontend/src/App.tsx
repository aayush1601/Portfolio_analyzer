import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, useApi, type Exposure, type PortfolioSummary, type Reference, type Risk, type Snapshot } from './api'
import { Actions } from './pages/Actions'
import { BacktestPage } from './pages/Backtest'
import { HoldingsEditor } from './pages/Holdings'
import { ImportPage, PhoneImport } from './pages/Import'
import { LookThrough } from './pages/LookThrough'
import { NewsPage } from './pages/News'
import { Overview } from './pages/Overview'
import { RiskPage } from './pages/Risk'
import { authEnabled, signOut } from './auth'
import { PlateContext, usePlates } from './plates'
import { Card, IconPlus, Mark, Status } from './ui'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'look-through', label: 'Look-through' },
  { id: 'risk', label: 'Risk' },
  { id: 'news', label: 'News' },
  { id: 'insights', label: 'Insights' },
  { id: 'backtest', label: 'Backtest' },
] as const
type Tab = (typeof TABS)[number]['id'] | 'new' | 'import'
const ALIASES: Record<string, Tab> = { holdings: 'overview', actions: 'insights' } // links from the previous build

function parseHash(): [Tab, string | null] {
  const [, raw, pid] = window.location.hash.split('?')[0].split('/') // ?view=… is page state, not route
  const tab = ALIASES[raw] ?? raw
  return [(TABS.some((x) => x.id === tab) || tab === 'new' || tab === 'import' ? tab : 'overview') as Tab, pid || null]
}

// Route: #/<tab>/<portfolio id>, so every view can be linked, bookmarked and reloaded.
function useRoute(): [Tab, string | null, (tab: Tab, pid?: string | null) => void] {
  const [route, setRoute] = useState(parseHash)
  useEffect(() => {
    const on = () => setRoute(parseHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (tab: Tab, pid: string | null = route[1]) => {
    window.location.hash = `/${tab}${pid ? `/${pid}` : ''}`
  }
  return [route[0], route[1], go]
}

export default function App() {
  const [tab, routePid, go] = useRoute()
  const reference = useApi<Reference>('/reference')
  const portfolios = useApi<PortfolioSummary[]>('/portfolio')
  // On #/import/<token> the second segment is a phone upload token, not a portfolio id.
  const phoneToken = tab === 'import' ? routePid : null
  const pid = (tab === 'import' ? null : routePid) ?? portfolios.data?.[0]?.portfolio_id ?? null
  const live = pid && tab !== 'new' && tab !== 'import'
  const snap = useApi<Snapshot>(live ? `/portfolio/${pid}` : null)
  const exposure = useApi<Exposure>(live ? `/portfolio/${pid}/exposure` : null)
  const risk = useApi<Risk>(live ? `/portfolio/${pid}/risk` : null)

  const effective = useMemo(
    () => Object.fromEntries((exposure.data?.companies ?? []).map((c) => [c.symbol, c.effective])),
    [exposure.data],
  )
  const plates = usePlates(reference.data, effective)
  const current = portfolios.data?.find((p) => p.portfolio_id === pid)

  useEffect(() => {
    document.title = current ? `${current.name} · Portfolio Intelligence` : 'Portfolio Intelligence'
  }, [current])

  const { reload: reloadPortfolios } = portfolios
  const { reload: reloadReference } = reference
  const afterImport = useCallback(() => {
    reloadPortfolios()
    reloadReference() // imported funds outside the universe join the reference list
  }, [reloadPortfolios, reloadReference])

  const refresh = () => {
    snap.reload()
    exposure.reload()
    risk.reload()
  }

  let page
  if (phoneToken) {
    page = <PhoneImport token={phoneToken} />
  } else if (tab === 'import') {
    page = <ImportPage onImported={afterImport} />
  } else if (tab === 'backtest') {
    page = <BacktestPage />
  } else if (!reference.data) {
    page = <Status<Reference> q={reference} what="the portfolio service">{() => null}</Status>
  } else if (!portfolios.data) {
    page = <Status<PortfolioSummary[]> q={portfolios} what="portfolios">{() => null}</Status>
  } else if (tab === 'new') {
    page = (
      <Card title="Start a new portfolio" dek="Add the stocks, funds and cash you hold. You can change them later from Overview.">
        <HoldingsEditor
          withName
          initial={[{ asset_type: 'CASH', asset_id: 'INR', quantity: 10000, avg_cost: 0 }]}
          reference={reference.data}
          onCancel={() => go('overview')}
          onSubmit={async (holdings, name) => {
            const r = await api<{ portfolio_id: string }>('/portfolio', { method: 'POST', body: JSON.stringify({ name, holdings }) })
            portfolios.reload()
            go('overview', r.portfolio_id)
          }}
        />
      </Card>
    )
  } else if (!pid) {
    page = <Card title="No portfolios yet" dek="Create one to see its look-through exposure, risk and news.">{null}</Card>
  } else if (tab === 'overview') {
    page = (
      <Status q={snap} what="your portfolio">
        {(s) => <Overview snap={s} exposure={exposure} risk={risk} reference={reference.data!} pid={pid} onSaved={refresh} />}
      </Status>
    )
  } else if (tab === 'look-through') {
    page = <Status q={exposure} what="look-through exposure">{(e) => <LookThrough exposure={e} reference={reference.data!} snapshot={snap.data} />}</Status>
  } else if (tab === 'risk') {
    page = <RiskPage pid={pid} reference={reference.data} />
  } else if (tab === 'news') {
    page = <NewsPage pid={pid} />
  } else {
    page = <Actions pid={pid} reference={reference.data} />
  }

  return (
    <PlateContext.Provider value={plates}>
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-panel/95 backdrop-blur-sm">
          <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-6 gap-y-2 px-4 pt-3 sm:px-8 md:flex-nowrap md:py-0">
            <a href="#/overview" className="flex shrink-0 items-center gap-2.5 text-ink no-underline md:py-3">
              <Mark className="size-8" />
              <span className="text-[1.05rem] font-extrabold tracking-[-0.01em]">Portfolio Intelligence</span>
            </a>
            <nav aria-label="Sections" className="no-print order-3 -mx-4 w-[calc(100%+2rem)] overflow-x-auto px-2 md:order-none md:mx-0 md:w-auto md:px-0">
              <ul className="flex">
                {TABS.map((t) => {
                  const active = tab === t.id
                  return (
                    <li key={t.id}>
                      <a
                        href={`#/${t.id}${pid ? `/${pid}` : ''}`}
                        aria-current={active ? 'page' : undefined}
                        className={`block border-b-[3px] px-3 py-3 text-[0.92rem] whitespace-nowrap no-underline transition-colors md:py-[1.15rem] ${
                          active ? 'border-brand font-extrabold text-ink' : 'border-transparent font-semibold text-ink-2 hover:text-ink'
                        }`}
                      >
                        {t.label}
                      </a>
                    </li>
                  )
                })}
              </ul>
            </nav>
            <div className="ml-auto flex min-w-0 items-center gap-2">
              <label className="sr-only" htmlFor="portfolio">
                Portfolio
              </label>
              <select
                id="portfolio"
                className="w-full max-w-[15rem] min-w-[9rem] rounded-full border border-line bg-canvas px-3 py-1.5 text-[0.88rem] font-bold text-ink hover:border-ink-3 focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
                value={pid ?? ''}
                onChange={(e) => go(tab === 'new' ? 'overview' : tab, e.target.value)}
                disabled={!portfolios.data}
              >
                {portfolios.data?.map((p) => (
                  <option key={p.portfolio_id} value={p.portfolio_id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <a
                href="#/import"
                className="no-print inline-flex shrink-0 items-center gap-1 rounded-full border border-line px-3 py-1.5 text-[0.85rem] font-bold whitespace-nowrap text-ink no-underline hover:border-ink-3"
              >
                Import funds
              </a>
              <button
                onClick={() => go('new', pid)}
                className="no-print inline-flex shrink-0 items-center gap-1 rounded-full bg-brand-ink px-3 py-1.5 text-[0.85rem] font-bold whitespace-nowrap text-white hover:bg-brand-deep"
              >
                <IconPlus className="size-3.5" title="New portfolio" /> <span className="hidden sm:inline">New portfolio</span>
              </button>
              {authEnabled && (
                <button onClick={signOut} className="no-print shrink-0 px-1 text-[0.85rem] font-bold whitespace-nowrap text-ink-2 hover:text-ink">
                  Sign out
                </button>
              )}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 py-6 sm:px-8">{page}</main>

        <footer className="mx-auto w-full max-w-[1240px] px-4 py-6 text-[0.78rem] text-ink-2 sm:px-8">
          Portfolio Intelligence is an academic decision-support and research system. Insights are hypothetical and are not financial advice.
        </footer>
      </div>
    </PlateContext.Provider>
  )
}
