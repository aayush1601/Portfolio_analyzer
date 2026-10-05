import { Dumbbell, SectorBars } from '../charts'
import type { Company, Exposure, Reference, Snapshot } from '../api'
import { companyHeadline, sectorHeadline, unseenFunds } from '../insights'
import { Avatar, Card, IconAlert, Legend, Notes, Plate, Table } from '../ui'
import { day, pct, pts } from '../format'

export function LookThrough({
  exposure: e,
  reference,
  snapshot,
}: {
  exposure: Exposure
  reference: Reference
  snapshot: Snapshot | null
}) {
  const { company: cCap, sector: sCap } = reference.caps
  const head = companyHeadline(e)
  const top = e.companies.slice(0, 10)
  const fundName = (code: string) => reference.funds.find((f) => f.scheme_code === code)?.name ?? code
  const unseen = unseenFunds(e, snapshot, reference)
  const months = Object.entries(e.holdings_as_of)
  const source = `Effective exposure = direct weight + Σ fund weight × the fund’s holding in that company. Prices to ${day(e.as_of)}; fund holdings: ${
    months.length ? months.map(([f, m]) => `${fundName(f)} (${m})`).join(', ') : 'no disclosures loaded yet'
  }.`

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
      <Card
        title={head.title}
        dek={head.dek}
        source={source}
        aside={
          <Legend
            items={[
              { swatch: 'bg-accent', label: 'held directly' },
              { swatch: 'hatch-via outline outline-1 outline-via', label: 'added by your funds' },
            ]}
          />
        }
      >
        {top.length ? (
          <Dumbbell rows={top} cap={cCap} unseen={unseen} />
        ) : (
          <p className="py-6 text-ink-2">This portfolio holds no companies yet: add stocks or funds from Overview → Edit.</p>
        )}
        {e.companies.length > top.length && (
          <p className="mt-3 text-[0.85rem] text-ink-3">Top {top.length} of {e.companies.length} companies by effective exposure; all are in the table below.</p>
        )}
      </Card>

      <Card
        title={sectorHeadline(e, sCap, unseen)}
        dek={`Dashed line: the ${pct(sCap, 0)} sector cap the recommendations enforce.`}
        source={`Sectors from the NIFTY 50 classification. Concentration: like holding ${e.n_effective ? Math.round(e.n_effective) : '–'} equally weighted companies (HHI ${e.hhi_effective.toFixed(3)}).`}
      >
        <SectorBars
          rows={e.sectors}
          cap={sCap}
          unmappedLabel={unseen.length === 1 ? `${unseen[0].label}, not yet visible` : undefined}
        />
      </Card>

      <Card
        className="lg:col-span-2"
        title="Every company you’re exposed to, and through which fund"
        dek="Sort by any column. Effective exposure above the single-company cap is flagged."
        source={e.notes.length ? <Notes notes={e.notes} /> : undefined}
      >
        <Table<Company>
          caption="Company exposure, direct and through funds"
          rows={e.companies}
          rowKey={(c) => c.symbol}
          initialSort={{ key: 'effective', dir: 'desc' }}
          columns={[
            {
              key: 'company',
              label: 'Company',
              render: (c) => (
                <span className="flex items-center gap-2.5">
                  <Avatar id={c.symbol} size="sm" />
                  <Plate id={c.symbol} compact />
                </span>
              ),
              sort: (c) => c.symbol,
            },
            {
              key: 'effective',
              label: 'Effective',
              align: 'right',
              render: (c) => (
                <span className={`num font-bold whitespace-nowrap ${c.effective > cCap ? 'text-loss' : ''}`}>
                  {c.effective > cCap && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
                  {pct(c.effective)}
                </span>
              ),
              sort: (c) => c.effective,
            },
            { key: 'direct', label: 'Direct', align: 'right', render: (c) => <span className="num">{pct(c.direct)}</span>, sort: (c) => c.direct },
            { key: 'indirect', label: 'Via funds', align: 'right', render: (c) => <span className="num font-bold text-via-ink">{c.indirect ? pts(c.indirect) : '–'}</span>, sort: (c) => c.indirect },
            { key: 'sector', label: 'Sector', render: (c) => <span className="text-ink-2">{c.sector}</span>, sort: (c) => c.sector },
            {
              key: 'via',
              label: 'Through',
              render: (c) =>
                c.via.length ? (
                  <span className="text-[0.85rem] text-ink-2">{c.via.map((v) => `${fundName(v.fund)} ${pts(v.contribution)}`).join(' · ')}</span>
                ) : (
                  <span className="text-ink-3">direct only</span>
                ),
            },
          ]}
        />
      </Card>

      {e.overlap.length > 0 && (
        <Card
          className="lg:col-span-2"
          title="How much your funds hold in common"
          dek="Overlap = the share of holdings two funds have in common (Σ min weight per security). High overlap means paying two fees for one portfolio."
        >
          <Table
            caption="Pairwise fund overlap"
            rows={e.overlap}
            rowKey={(o) => o.fund_a + o.fund_b}
            initialSort={{ key: 'overlap', dir: 'desc' }}
            columns={[
              { key: 'a', label: 'Fund', render: (o) => fundName(o.fund_a) },
              { key: 'b', label: 'and fund', render: (o) => fundName(o.fund_b) },
              { key: 'overlap', label: 'Overlap', align: 'right', render: (o) => <span className="num">{pct(o.overlap)}</span>, sort: (o) => o.overlap },
            ]}
          />
        </Card>
      )}
    </div>
  )
}
