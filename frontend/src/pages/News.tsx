import { useState } from 'react'
import { SignedBar } from '../charts'
import { useApi, type NewsAlert, type NewsItem, type PortfolioNews } from '../api'
import { dateTime, fixed, pct, signed } from '../format'
import { reorder, slug } from '../motion'
import { Avatar, Card, Chip, IconAlert, IconExternal, Notes, Plate, Segmented, Status } from '../ui'

const SOURCE: Record<string, string> = {
  economictimes_markets: 'Economic Times',
  moneycontrol_business: 'Moneycontrol',
  livemint_markets: 'Mint',
}
const SENTIMENT_TONE = { positive: 'gain', negative: 'loss', neutral: 'neutral' } as const

function headline(n: PortfolioNews) {
  const v = n.portfolio_news_impact
  const lean = v > 0.005 ? 'leans positive' : v < -0.005 ? 'leans negative' : 'is roughly neutral'
  return `News from the last ${n.lookback_hours} hours ${lean} for this portfolio (impact ${signed(v, 3)}).`
}

type Order = 'impact' | 'latest'

function Item({ i, max }: { i: NewsItem; max: number }) {
  return (
    <li className="grid gap-x-6 gap-y-3 px-5 py-4 sm:px-6 md:grid-cols-[minmax(0,1fr)_13rem]" style={{ viewTransitionName: `news-${slug(i.news_id)}` }}>
      <div className="min-w-0">
        <a href={i.url} target="_blank" rel="noreferrer" className="block font-bold text-ink no-underline hover:text-accent-ink">
          {i.headline}
          <IconExternal className="ml-1 inline size-3 -translate-y-px text-ink-3" title="opens the article" />
        </a>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[0.78rem] text-ink-3">
            {SOURCE[i.source] ?? i.source} · <span className="num">{dateTime(i.published_at)}</span>
          </span>
          {i.matched_via === 'company' ? (
            i.symbols.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5 rounded-full border border-line py-0.5 pr-2.5 pl-0.5 text-[0.8rem]">
                <Avatar id={s} size="sm" />
                <Plate id={s} compact />
              </span>
            ))
          ) : (
            <Chip>Through your sector: {i.sectors.join(', ')}</Chip>
          )}
        </div>
      </div>
      <div className="flex flex-row items-center justify-between gap-3 md:flex-col md:items-end md:justify-start">
        <Chip tone={SENTIMENT_TONE[i.sentiment.label as keyof typeof SENTIMENT_TONE] ?? 'neutral'}>
          {i.sentiment.label[0].toUpperCase() + i.sentiment.label.slice(1)} <span className="num">{signed(i.sentiment.score)}</span>
        </Chip>
        <div className="flex w-full max-w-[13rem] items-center gap-2">
          <SignedBar value={i.impact} max={max} label={`impact ${fixed(i.impact, 3)}`} />
          <span className="num w-14 shrink-0 text-right text-[0.88rem] font-bold">{signed(i.impact, 3)}</span>
        </div>
        <p className="hidden text-[0.75rem] text-ink-3 md:block">exposure {pct(i.effective_exposure)}</p>
      </div>
    </li>
  )
}

/** Alerts the news_impact job raised (and emailed, when SNS is set up) for this portfolio. Hidden until the AWS job has sent any. */
function Alerts({ pid }: { pid: string }) {
  const q = useApi<NewsAlert[]>('/portfolio/alerts?limit=100')
  const mine = (q.data ?? []).filter((a) => a.portfolio_id === pid)
  if (mine.length === 0) return null
  return (
    <Card
      title={`${mine.length === 1 ? 'One negative-news alert' : `${mine.length} negative-news alerts`} raised for this portfolio, the latest on ${dateTime(mine[0].created_at)}.`}
      dek="Sent when portfolio impact crosses the alert threshold, at most once a day per portfolio."
    >
      <ul>
        {mine.map((a) => (
          <li key={a.created_at} className="flex items-center justify-between gap-3 border-b border-line-soft py-1.5 text-[0.9rem]">
            <span className="flex items-center gap-2">
              <IconAlert className="size-4 shrink-0 text-loss" />
              <span className="num text-ink-2">{dateTime(a.created_at)}</span>
            </span>
            <span className="num font-bold">impact {signed(a.impact, 3)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function NewsPage({ pid }: { pid: string }) {
  const q = useApi<PortfolioNews>(`/portfolio/${pid}/news?limit=100`)
  const [order, setOrder] = useState<Order>('impact')
  return (
    <Status q={q} what="portfolio news">
      {(n) => {
        const max = Math.max(...n.items.map((i) => Math.abs(i.impact)), 0.001)
        const items =
          order === 'impact' ? n.items : [...n.items].sort((a, b) => b.published_at.localeCompare(a.published_at))
        return (
          <div className="mx-auto max-w-5xl space-y-5">
            {n.alert && (
              <div role="alert" className="flex items-start gap-3 rounded-[var(--radius-card)] border border-loss/30 bg-loss-soft px-5 py-4">
                <IconAlert className="mt-0.5 size-5 shrink-0 text-loss" />
                <p>
                  <span className="font-bold text-loss">Negative news alert.</span> Portfolio impact {signed(n.portfolio_news_impact, 3)} is past the{' '}
                  {signed(-n.alert_threshold, 2)} threshold.
                </p>
              </div>
            )}
            <Card
              title={headline(n)}
              dek="Impact = FinBERT sentiment × importance × recency × source reliability × your effective exposure. News about a company you hold through a fund counts; news about a peer counts at half weight through its sector."
              aside={
                <Segmented<Order>
                  label="Order"
                  options={[
                    { value: 'impact', label: 'Most impact' },
                    { value: 'latest', label: 'Latest' },
                  ]}
                  value={order}
                  onChange={(o) => reorder(() => setOrder(o))}
                />
              }
              source={
                <>
                  Headlines from Economic Times, Moneycontrol and Mint RSS, collected every 30 minutes (near-real-time). Sentiment model: ProsusAI/finbert.
                  {n.notes.length > 0 && (
                    <span className="mt-1 block">
                      <Notes notes={n.notes} />
                    </span>
                  )}
                </>
              }
            >
              {n.items.length === 0 ? (
                <p className="py-6 text-ink-2">No news in this window touches anything this portfolio holds, directly or through its funds.</p>
              ) : (
                <ul className="-mx-5 divide-y divide-line-soft border-t border-line sm:-mx-6">
                  {items.map((i) => (
                    <Item key={i.news_id} i={i} max={max} />
                  ))}
                </ul>
              )}
            </Card>
            <Alerts pid={pid} />
          </div>
        )
      }}
    </Status>
  )
}
