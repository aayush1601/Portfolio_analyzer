// Plain-language findings shared by Overview and Look-through, so both tell the same story.
import type { Exposure, Reference, Snapshot } from './api'
import { pct, pts } from './format'

export const UNMAPPED = 'Other/Unmapped'
export type Unseen = { id: string; label: string; weight: number }

/** Funds held without an ingested disclosure: shown as their own grey rows, never guessed. */
export function unseenFunds(e: Exposure, snapshot: Snapshot | null, reference: Reference): Unseen[] {
  return (snapshot?.holdings ?? [])
    .filter((h) => h.asset_type === 'MF' && !(h.asset_id in e.holdings_as_of))
    .map((h) => {
      const f = reference.funds.find((x) => x.scheme_code === h.asset_id)
      return { id: h.asset_id, label: f ? `${f.name} (${f.category})` : h.asset_id, weight: h.weight }
    })
}

export function companyHeadline(e: Exposure): { title: string; dek: string } {
  const gap = [...e.companies].sort((a, b) => b.indirect - a.indirect)[0]
  if (gap && gap.indirect > 0.0005) {
    return gap.direct > 0
      ? {
          title: `Your funds add ${pts(gap.indirect)} of ${gap.symbol}: you carry ${pct(gap.effective)}, not the ${pct(gap.direct)} on your statement.`,
          dek: 'The dot is what you hold directly; the ring is what you hold once every fund is opened up.',
        }
      : {
          title: `You own no ${gap.symbol} shares, yet your funds give you ${pct(gap.effective)} of it.`,
          dek: 'The ring is what you hold once every fund is opened up.',
        }
  }
  if (e.unmapped > 0.0005) {
    return {
      title: `${pct(e.unmapped, 0)} of this portfolio sits inside funds we can’t see into yet.`,
      dek: 'Look-through needs each fund’s monthly holdings disclosure. Until one is loaded, that fund is shown as “not yet visible” instead of being guessed.',
    }
  }
  return { title: 'Everything you hold is visible: direct and effective exposure match.', dek: 'No fund adds hidden exposure here.' }
}

export function sectorHeadline(e: Exposure, cap: number, unseen: Unseen[]): string {
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
