import { SignedBar } from '../charts'
import { useApi, type NewsItem, type PortfolioNews } from '../api'
import { Figure, IconAlert, IconExternal, Notes, Plate, Status, Table } from '../ui'
import { dateTime, fixed, pct, signed } from '../format'

const SOURCE: Record<string, string> = {
  economictimes_markets: 'Economic Times',
  moneycontrol_business: 'Moneycontrol',
  livemint_markets: 'Mint',
}

function headline(n: PortfolioNews) {
  const v = n.portfolio_news_impact
  const lean = v > 0.005 ? 'leans positive' : v < -0.005 ? 'leans negative' : 'is roughly neutral'
  return `News from the last ${n.lookback_hours} hours ${lean} for this portfolio (impact ${signed(v, 3)}).`
}

export function NewsPage({ pid }: { pid: string }) {
  const q = useApi<PortfolioNews>(`/portfolio/${pid}/news?limit=100`)
  return (
    <Status q={q} what="portfolio news">
      {(n) => {
        const max = Math.max(...n.items.map((i) => Math.abs(i.impact)), 0.001)
        return (
          <div className="space-y-5">
            {n.alert && (
              <div role="alert" className="flex items-start gap-3 border-t-2 border-alert bg-alert-soft px-5 py-3 sm:px-6">
                <IconAlert className="mt-0.5 size-5 shrink-0 text-alert" />
                <p>
                  <span className="font-semibold text-alert">Negative news alert.</span> Portfolio impact {signed(n.portfolio_news_impact, 3)} is past the{' '}
                  {signed(-n.alert_threshold, 2)} threshold.
                </p>
              </div>
            )}
            <Figure
              title={headline(n)}
              dek="Impact = FinBERT sentiment × importance × recency × source reliability × your effective exposure. A company you hold through funds counts; news about a peer counts at half weight through its sector."
              source={
                <>
                  Headlines from Economic Times, Moneycontrol and Mint RSS, collected every 30 minutes (near-real-time). Sentiment model: ProsusAI/finbert.
                  {n.notes.length > 0 && <span className="mt-1 block"><Notes notes={n.notes} /></span>}
                </>
              }
            >
              {n.items.length === 0 ? (
                <p className="py-6 text-ink-2">No news in this window touches anything this portfolio holds, directly or through its funds.</p>
              ) : (
                <Table<NewsItem>
                  caption="News ranked by impact on this portfolio"
                  rows={n.items}
                  rowKey={(i) => i.news_id}
                  initialSort={{ key: 'impact', dir: 'desc' }}
                  columns={[
                    { key: 'when', label: 'Published', render: (i) => <span className="num text-[0.8rem] whitespace-nowrap text-ink-2">{dateTime(i.published_at)}</span>, sort: (i) => i.published_at },
                    {
                      key: 'headline',
                      label: 'Headline',
                      className: 'min-w-[18rem] max-w-[34rem]',
                      render: (i) => (
                        <>
                          <a href={i.url} target="_blank" rel="noreferrer" className="font-semibold text-ink hover:underline">
                            {i.headline}
                            <IconExternal className="ml-1 inline size-3 -translate-y-px text-ink-3" title="opens the article" />
                          </a>
                          <span className="block text-[0.8rem] text-ink-3">{SOURCE[i.source] ?? i.source}</span>
                        </>
                      ),
                    },
                    {
                      key: 'names',
                      label: 'Reaches you through',
                      render: (i) =>
                        i.matched_via === 'company' ? (
                          <span className="flex flex-col gap-0.5 text-[0.85rem]">{i.symbols.map((s) => <Plate key={s} id={s} />)}</span>
                        ) : (
                          <span className="text-[0.85rem] text-ink-2">sector: {i.sectors.join(', ')}</span>
                        ),
                    },
                    {
                      key: 'sentiment',
                      label: 'Sentiment',
                      render: (i) => (
                        <span className="text-[0.85rem] whitespace-nowrap">
                          {i.sentiment.label} <span className="num text-ink-2">{signed(i.sentiment.score)}</span>
                        </span>
                      ),
                      sort: (i) => i.sentiment.score,
                    },
                    { key: 'exposure', label: 'Exposure', align: 'right', render: (i) => <span className="num">{pct(i.effective_exposure)}</span>, sort: (i) => i.effective_exposure },
                    {
                      key: 'impact',
                      label: 'Impact',
                      align: 'right',
                      render: (i) => (
                        <span className="flex items-center justify-end gap-2">
                          <span className="w-20"><SignedBar value={i.impact} max={max} label={`impact ${fixed(i.impact, 3)}`} /></span>
                          <span className="num w-16 text-right">{signed(i.impact, 3)}</span>
                        </span>
                      ),
                      sort: (i) => Math.abs(i.impact),
                    },
                  ]}
                />
              )}
            </Figure>
          </div>
        )
      }}
    </Status>
  )
}
