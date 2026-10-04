import { Dumbbell, SectorBars } from '../charts'
import type { Company, Exposure, Reference, Snapshot } from '../api'
import { Figure, IconAlert, Legend, Notes, Plate, Table } from '../ui'
import { day, pct, pts } from '../format'

const UNMAPPED = 'Other/Unmapped'

function companyHeadline(e: Exposure): { title: string; dek: string } {
  const gap = [...e.companies].sort((a, b) => b.indirect - a.indirect)[0]
  if (gap && gap.indirect > 0.0005) {
    return gap.direct > 0
      ? {
          title: `Your funds add ${pts(gap.indirect)} of ${gap.symbol}: you carry ${pct(gap.effective)}, not the ${pct(gap.direct)} on your statement.`,
          dek: 'Each row is one company. The dot is what you hold directly; the ring is what you hold once every fund is opened up.',
        }
      : {
          title: `You own no ${gap.symbol} shares, yet your funds give you ${pct(gap.effective)} of it.`,
          dek: 'Each row is one company. The ring is what you hold once every fund is opened up.',
        }
  }
  if (e.unmapped > 0.0005) {
    return {
      title: `${pct(e.unmapped, 0)} of this portfolio sits inside funds we can’t see into yet.`,
      dek: 'Look-through needs each fund’s monthly holdings disclosure. Until one is loaded, that fund is shown as “not yet visible” instead of being guessed. Below: the companies you hold directly.',
    }
  }
  return { title: 'Everything you hold is visible: direct and effective exposure match.', dek: 'No fund adds hidden exposure here.' }
}

type Unseen = { label: string; weight: number }

function sectorHeadline(e: Exposure, cap: number, unseen: Unseen[]): string {
  const real = e.sectors.filter((s) => s.sector !== UNMAPPED)
  const hidden = unseen.reduce((a, u) => a + u.weight, 0)
  // Never crown a "largest sector" while a bigger block is still unopened: that fund may change the answer.
  if (hidden > (real[0]?.effective ?? 0)) {
    const what = unseen.length === 1 ? `a ${pct(hidden)} ${unseen[0].label}` : `${pct(hidden)} in ${unseen.length} funds`
    return real[0]
      ? `${real[0].sector} is ${pct(real[0].effective)} of what’s visible, and ${what} isn’t opened up yet.`
      : `${what[0].toUpperCase()}${what.slice(1)} isn’t opened up yet.`
  }
  const widened = [...real].sort((a, b) => b.effective - b.direct - (a.effective - a.direct))[0]
  if (widened && widened.effective - widened.direct > 0.0005)
    return `${widened.sector} is ${pct(widened.effective)} of the portfolio once funds are counted, up from ${pct(widened.direct)}.`
  const top = real[0]
  if (!top) return 'No sector exposure is visible yet.'
  return `${top.sector} is the largest sector at ${pct(top.effective)}${top.effective > cap ? `, above the ${pct(cap, 0)} sector cap` : ''}.`
}

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
  // Funds held without an ingested disclosure: drawn as their own grey rows, never guessed.
  const unseen: Unseen[] = (snapshot?.holdings ?? [])
    .filter((h) => h.asset_type === 'MF' && !(h.asset_id in e.holdings_as_of))
    .map((h) => {
      const f = reference.funds.find((x) => x.scheme_code === h.asset_id)
      return { label: f ? `${f.name} (${f.category})` : h.asset_id, weight: h.weight }
    })
  const months = Object.entries(e.holdings_as_of)
  const source = `Effective exposure = direct weight + Σ fund weight × the fund’s holding in that company. Prices to ${day(e.as_of)}; fund holdings: ${
    months.length ? months.map(([f, m]) => `${fundName(f)} (${m})`).join(', ') : 'no disclosures loaded yet'
  }.`

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
      <Figure
        title={head.title}
        dek={head.dek}
        source={source}
        aside={
          <Legend
            items={[
              { swatch: 'bg-direct', label: 'held directly' },
              { swatch: 'hatch-via outline outline-1 outline-via', label: 'added by your funds' },
            ]}
          />
        }
      >
        {top.length ? (
          <Dumbbell rows={top} cap={cCap} unseen={unseen} />
        ) : (
          <p className="py-6 text-ink-2">This portfolio holds no companies yet: add stocks or funds on the Holdings tab.</p>
        )}
        {e.companies.length > top.length && (
          <p className="mt-3 text-[0.85rem] text-ink-3">Top {top.length} of {e.companies.length} companies by effective exposure; all are in the table below.</p>
        )}
      </Figure>

      <Figure
        title={sectorHeadline(e, sCap, unseen)}
        dek={`Dashed line: the ${pct(sCap, 0)} sector cap the recommendations enforce.`}
        source={`Sectors from the NIFTY 50 classification. Concentration: like holding ${e.n_effective ? Math.round(e.n_effective) : '–'} equally weighted companies (HHI ${e.hhi_effective.toFixed(3)}).`}
      >
        <SectorBars
          rows={e.sectors}
          cap={sCap}
          unmappedLabel={unseen.length === 1 ? `${unseen[0].label}, not yet visible` : undefined}
        />
      </Figure>

      <Figure
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
            { key: 'company', label: 'Company', render: (c) => <Plate id={c.symbol} compact />, sort: (c) => c.symbol },
            {
              key: 'effective',
              label: 'Effective',
              align: 'right',
              render: (c) => (
                <span className={`num font-semibold whitespace-nowrap ${c.effective > cCap ? 'text-alert' : ''}`}>
                  {c.effective > cCap && <IconAlert className="mr-1 inline size-3.5 -translate-y-px" title="above cap" />}
                  {pct(c.effective)}
                </span>
              ),
              sort: (c) => c.effective,
            },
            { key: 'direct', label: 'Direct', align: 'right', render: (c) => <span className="num">{pct(c.direct)}</span>, sort: (c) => c.direct },
            { key: 'indirect', label: 'Via funds', align: 'right', render: (c) => <span className="num text-via">{c.indirect ? pts(c.indirect) : '–'}</span>, sort: (c) => c.indirect },
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
      </Figure>

      {e.overlap.length > 0 && (
        <Figure
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
        </Figure>
      )}
    </div>
  )
}
