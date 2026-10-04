import { useEffect, useMemo, useState } from 'react'
import { api, useApi, type Exposure, type PortfolioSummary, type Reference, type Risk, type Snapshot } from './api'
import { day, inr, signedInr } from './format'
import { Actions } from './pages/Actions'
import { Holdings, HoldingsEditor } from './pages/Holdings'
import { LookThrough } from './pages/LookThrough'
import { NewsPage } from './pages/News'
import { RiskPage } from './pages/Risk'
import { PlateContext, usePlates } from './plates'
import { Delta, Figure, IconPlus, Status } from './ui'

const TABS = [
  { id: 'look-through', label: 'Look-through' },
  { id: 'holdings', label: 'Holdings' },
  { id: 'risk', label: 'Risk' },
  { id: 'news', label: 'News' },
  { id: 'actions', label: 'Actions' },
] as const
type Tab = (typeof TABS)[number]['id'] | 'new'

function parseHash(): [Tab, string | null] {
  const [, tab, pid] = window.location.hash.split('/')
  return [(TABS.some((x) => x.id === tab) || tab === 'new' ? tab : 'look-through') as Tab, pid || null]
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

function FiguresStrip({ snap, risk }: { snap: Snapshot | null; risk: Risk | null }) {
  const cell = 'flex min-w-0 flex-col gap-0.5 border-rule py-2.5 sm:border-l sm:px-5 sm:first:border-l-0 sm:first:pl-0'
  const label = 'text-[0.75rem] text-ink-2'
  const value = 'num text-[1.05rem] font-semibold text-ink'
  return (
    <div className="grid grid-cols-2 gap-x-4 border-b border-rule bg-panel px-5 sm:flex sm:flex-wrap sm:gap-x-0 sm:px-8">
      <div className={cell}>
        <span className={label}>Value{snap ? `, ${day(snap.as_of)}` : ''}</span>
        <span className={value}>{snap ? inr(snap.total_value) : '…'}</span>
      </div>
      <div className={cell}>
        <span className={label}>Today</span>
        <span className={value}>{snap ? <Delta value={snap.daily_pl}>{signedInr(snap.daily_pl)}</Delta> : '…'}</span>
      </div>
      <div className={cell}>
        <span className={label}>Since purchase</span>
        <span className={value}>{snap ? <Delta value={snap.total_pl}>{signedInr(snap.total_pl)}</Delta> : '…'}</span>
      </div>
      <div className={cell}>
        <span className={label}>Risk score, 1 year</span>
        <span className={value}>
          {risk ? (
            <>
              {risk.risk_score}
              <span className="font-sans text-[0.85rem] font-normal text-ink-2"> /100 · {risk.risk_band}</span>
            </>
          ) : (
            '…'
          )}
        </span>
      </div>
    </div>
  )
}

export default function App() {
  const [tab, routePid, go] = useRoute()
  const reference = useApi<Reference>('/reference')
  const portfolios = useApi<PortfolioSummary[]>('/portfolio')
  const pid = routePid ?? portfolios.data?.[0]?.portfolio_id ?? null
  const live = pid && tab !== 'new'
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

  const refresh = () => {
    snap.reload()
    exposure.reload()
    risk.reload()
  }

  let page
  if (!reference.data) {
    page = <Status<Reference> q={reference} what="the portfolio service">{() => null}</Status>
  } else if (!portfolios.data) {
    page = <Status<PortfolioSummary[]> q={portfolios} what="portfolios">{() => null}</Status>
  } else if (tab === 'new') {
    page = (
      <Figure title="Start a new portfolio" dek="Add the stocks, funds and cash you hold. You can change them later on the Holdings tab.">
        <HoldingsEditor
          withName
          initial={[{ asset_type: 'CASH', asset_id: 'INR', quantity: 10000, avg_cost: 0 }]}
          reference={reference.data}
          onCancel={() => go('look-through')}
          onSubmit={async (holdings, name) => {
            const r = await api<{ portfolio_id: string }>('/portfolio', { method: 'POST', body: JSON.stringify({ name, holdings }) })
            portfolios.reload()
            go('holdings', r.portfolio_id)
          }}
        />
      </Figure>
    )
  } else if (!pid) {
    page = <Figure title="No portfolios yet" dek="Create one to see its look-through exposure, risk and news.">{null}</Figure>
  } else if (tab === 'look-through') {
    page = <Status q={exposure} what="look-through exposure">{(e) => <LookThrough exposure={e} reference={reference.data!} snapshot={snap.data} />}</Status>
  } else if (tab === 'holdings') {
    page = <Status q={snap} what="holdings">{(s) => <Holdings snapshot={s} reference={reference.data!} onSaved={refresh} />}</Status>
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
        <header className="bg-bar text-bar-ink">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 pt-3 sm:px-8">
            <a href="#/look-through" className="text-[1.05rem] font-bold tracking-[-0.01em] text-bar-ink no-underline">
              Portfolio Intelligence
            </a>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <label className="sr-only" htmlFor="portfolio">Portfolio</label>
              <select
                id="portfolio"
                className="w-full max-w-[18rem] min-w-[9rem] rounded-[3px] border border-white/25 bg-white/10 px-2 py-1 text-[0.9rem] text-bar-ink hover:border-white/50 focus:outline-none [&>option]:text-ink"
                value={pid ?? ''}
                onChange={(e) => go(tab === 'new' ? 'look-through' : tab, e.target.value)}
                disabled={!portfolios.data}
              >
                {portfolios.data?.map((p) => (
                  <option key={p.portfolio_id} value={p.portfolio_id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => go('new', pid)}
                className="no-print inline-flex items-center gap-1 rounded-[3px] px-2 py-1 text-[0.85rem] whitespace-nowrap text-bar-ink-2 hover:bg-white/10 hover:text-bar-ink"
              >
                <IconPlus className="size-3.5" title="New portfolio" /> <span className="hidden sm:inline">New portfolio</span>
              </button>
            </div>
            <p className="hidden text-[0.8rem] text-bar-ink-2 md:block">Prices to {snap.data ? day(snap.data.as_of) : '…'} · news near-real-time</p>
          </div>
          <nav aria-label="Sections" className="no-print mt-2 overflow-x-auto px-3 sm:px-6">
            <ul className="flex">
              {TABS.map((t) => {
                const active = tab === t.id
                return (
                  <li key={t.id}>
                    <a
                      href={`#/${t.id}${pid ? `/${pid}` : ''}`}
                      aria-current={active ? 'page' : undefined}
                      className={`block border-b-[3px] px-3 py-2 text-[0.95rem] whitespace-nowrap no-underline transition-colors ${
                        active ? 'border-bar-ink font-semibold text-bar-ink' : 'border-transparent text-bar-ink-2 hover:text-bar-ink'
                      }`}
                    >
                      {t.label}
                    </a>
                  </li>
                )
              })}
            </ul>
          </nav>
        </header>

        {tab !== 'new' && <FiguresStrip snap={snap.data} risk={risk.data} />}

        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-8">{page}</main>

        <footer className="border-t border-rule px-5 py-4 text-[0.8rem] text-ink-3 sm:px-8">
          Portfolio Intelligence is an academic decision-support and research system. Recommendations are hypothetical and are not
          financial advice.
        </footer>
      </div>
    </PlateContext.Provider>
  )
}
