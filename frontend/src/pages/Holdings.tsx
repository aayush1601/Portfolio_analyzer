import { useState } from 'react'
import { WeightStrip } from '../charts'
import { api, type AssetType, type Holding, type HoldingValue, type Reference, type Snapshot } from '../api'
import { Button, Delta, Figure, IconPlus, IconTrash, Plate, Table } from '../ui'
import { day, inr, inr2, pct, signedInr } from '../format'

const TYPE_LABEL: Record<AssetType, string> = { STOCK: 'Stock', MF: 'Fund', CASH: 'Cash' }
const field =
  'w-full rounded-[3px] border border-rule bg-panel px-2 py-1.5 text-[0.9rem] text-ink hover:border-ink-3 focus:border-direct focus:outline-none'

type Draft = { asset_type: AssetType; asset_id: string; quantity: string; avg_cost: string }
const toDraft = (h: Holding): Draft => ({
  asset_type: h.asset_type,
  asset_id: h.asset_id,
  quantity: String(h.quantity),
  avg_cost: h.asset_type === 'CASH' ? '' : String(h.avg_cost),
})

/** Edits a holdings list; used for both "edit holdings" and "new portfolio". */
export function HoldingsEditor({
  initial,
  reference,
  withName,
  onSubmit,
  onCancel,
}: {
  initial: Holding[]
  reference: Reference
  withName?: boolean
  onSubmit: (holdings: Holding[], name: string) => Promise<void>
  onCancel: () => void
}) {
  const [rows, setRows] = useState<Draft[]>(initial.map(toDraft))
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const set = (i: number, patch: Partial<Draft>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  const firstId = (t: AssetType) => (t === 'STOCK' ? reference.stocks[0].symbol : t === 'MF' ? reference.funds[0].scheme_code : 'INR')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const holdings = rows.map((r) => ({
      asset_type: r.asset_type,
      asset_id: r.asset_id,
      quantity: Number(r.quantity),
      avg_cost: r.asset_type === 'CASH' ? 0 : Number(r.avg_cost || 0),
    }))
    const bad = holdings.findIndex((h) => !(h.quantity > 0) || h.avg_cost < 0 || Number.isNaN(h.avg_cost))
    if (bad >= 0) return setError(`Row ${bad + 1}: quantity must be more than 0 and average cost can’t be negative.`)
    setSaving(true)
    try {
      await onSubmit(holdings, name.trim())
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {withName && (
        <label className="block max-w-sm">
          <span className="mb-1 block text-[0.85rem] font-semibold text-ink-2">Portfolio name</span>
          <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={field} placeholder="e.g. Retirement" />
        </label>
      )}
      <div className="-mx-5 overflow-x-auto sm:-mx-6">
        <table className="w-full min-w-[640px] text-[0.9rem]">
          <caption className="sr-only">Editable holdings</caption>
          <thead>
            <tr className="border-b border-ink text-left text-[0.8rem] text-ink-2">
              <th scope="col" className="w-28 py-2 pr-2 pl-5 font-semibold sm:pl-6">Type</th>
              <th scope="col" className="py-2 pr-2 font-semibold">Asset</th>
              <th scope="col" className="w-32 py-2 pr-2 font-semibold">Quantity / units</th>
              <th scope="col" className="w-36 py-2 pr-2 font-semibold">Avg cost per unit (₹)</th>
              <th scope="col" className="w-12 py-2 pr-5 sm:pr-6"><span className="sr-only">Remove</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-rule-soft">
                <td className="py-2 pr-2 pl-5 sm:pl-6">
                  <select
                    aria-label={`Row ${i + 1} type`}
                    className={field}
                    value={r.asset_type}
                    onChange={(e) => {
                      const t = e.target.value as AssetType
                      set(i, { asset_type: t, asset_id: firstId(t), avg_cost: t === 'CASH' ? '' : r.avg_cost })
                    }}
                  >
                    <option value="STOCK">Stock</option>
                    <option value="MF">Fund</option>
                    <option value="CASH">Cash</option>
                  </select>
                </td>
                <td className="py-2 pr-2">
                  {r.asset_type === 'CASH' ? (
                    <span className="text-ink-2">Indian rupees</span>
                  ) : (
                    <select aria-label={`Row ${i + 1} asset`} className={field} value={r.asset_id} onChange={(e) => set(i, { asset_id: e.target.value })}>
                      {r.asset_type === 'STOCK'
                        ? reference.stocks.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)
                        : reference.funds.map((f) => <option key={f.scheme_code} value={f.scheme_code}>{f.name} ({f.category})</option>)}
                    </select>
                  )}
                </td>
                <td className="py-2 pr-2">
                  <input aria-label={`Row ${i + 1} quantity`} inputMode="decimal" className={`${field} num`} value={r.quantity} onChange={(e) => set(i, { quantity: e.target.value })} />
                </td>
                <td className="py-2 pr-2">
                  <input
                    aria-label={`Row ${i + 1} average cost`}
                    inputMode="decimal"
                    disabled={r.asset_type === 'CASH'}
                    className={`${field} num disabled:bg-ground disabled:text-ink-3`}
                    value={r.avg_cost}
                    placeholder={r.asset_type === 'CASH' ? 'n/a' : ''}
                    onChange={(e) => set(i, { avg_cost: e.target.value })}
                  />
                </td>
                <td className="py-2 pr-5 text-right sm:pr-6">
                  <button type="button" aria-label={`Remove row ${i + 1}`} className="p-1 text-ink-3 hover:text-ink" onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>
                    <IconTrash />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Button type="button" onClick={() => setRows((r) => [...r, { asset_type: 'STOCK', asset_id: firstId('STOCK'), quantity: '', avg_cost: '' }])}>
        <IconPlus /> Add holding
      </Button>
      {error && (
        <p role="alert" className="text-alert">
          {error}
        </p>
      )}
      <div className="flex gap-2 border-t border-rule-soft pt-4">
        <Button variant="primary" type="submit" disabled={saving || rows.length === 0}>
          {saving ? 'Saving…' : withName ? 'Create portfolio' : 'Save holdings'}
        </Button>
        <Button type="button" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

export function Holdings({
  snapshot: s,
  reference,
  onSaved,
}: {
  snapshot: Snapshot
  reference: Reference
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const stale = (h: HoldingValue) => h.price_date && h.price_date !== s.as_of

  if (editing)
    return (
      <Figure title="Edit holdings" dek="Only NIFTY 50 stocks and the 15 research-universe funds can be added. Average cost is per share or unit, in today’s split-adjusted terms.">
        <HoldingsEditor
          initial={s.holdings}
          reference={reference}
          onCancel={() => setEditing(false)}
          onSubmit={async (holdings) => {
            await api(`/portfolio/${s.portfolio_id}/holdings`, { method: 'PUT', body: JSON.stringify(holdings) })
            setEditing(false)
            onSaved()
          }}
        />
      </Figure>
    )

  return (
    <Figure
      title={`Worth ${inr(s.total_value)} on ${day(s.as_of)}, ${s.total_pl >= 0 ? 'up' : 'down'} ${inr(Math.abs(s.total_pl))} on what it cost.`}
      dek={`Today’s move: ${signedInr(s.daily_pl)}. Fund NAVs publish around 23:00 IST, so a fund can lag the stock prices by a day.`}
      aside={<Button className="no-print" onClick={() => setEditing(true)}>Edit holdings</Button>}
      source="Prices: NSE closes via Yahoo Finance (split-adjusted). NAVs: AMFI via mfapi.in. P&L is unrealised, before costs and tax."
    >
      <WeightStrip
        rows={s.holdings.map((h) => ({
          id: h.asset_type + h.asset_id,
          kind: h.asset_type,
          weight: h.weight,
          label: h.asset_type === 'CASH' ? 'Cash' : h.asset_type === 'MF' ? reference.funds.find((f) => f.scheme_code === h.asset_id)?.name ?? h.asset_id : h.asset_id,
        }))}
      />
      <div className="mt-2 mb-5 flex flex-wrap gap-x-4 text-[0.8rem] text-ink-2">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-4 bg-direct" />stocks</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="hatch-via inline-block h-2.5 w-4 outline outline-1 outline-via" />funds</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-4 bg-rule" />cash</span>
      </div>
      <Table<HoldingValue>
        caption="Holdings with valuation and profit and loss"
        rows={s.holdings}
        rowKey={(h) => h.asset_type + h.asset_id}
        initialSort={{ key: 'value', dir: 'desc' }}
        columns={[
          {
            key: 'asset',
            label: 'Holding',
            render: (h) => (h.asset_type === 'CASH' ? <span className="font-semibold">Cash</span> : <Plate id={h.asset_id} compact />),
            sort: (h) => h.asset_id,
          },
          { key: 'type', label: 'Type', render: (h) => <span className="text-ink-2">{TYPE_LABEL[h.asset_type]}</span>, sort: (h) => h.asset_type },
          { key: 'qty', label: 'Quantity', align: 'right', render: (h) => <span className="num">{h.quantity.toLocaleString('en-IN')}</span>, sort: (h) => h.quantity },
          { key: 'cost', label: 'Avg cost', align: 'right', render: (h) => (h.asset_type === 'CASH' ? '–' : <span className="num">{inr2(h.avg_cost)}</span>) },
          {
            key: 'price',
            label: 'Price',
            align: 'right',
            render: (h) =>
              h.asset_type === 'CASH' ? '–' : (
                <span className="num">
                  {inr2(h.price)}
                  {stale(h) && <span className="block text-[0.75rem] text-ink-3">as of {day(h.price_date!)}</span>}
                </span>
              ),
          },
          { key: 'value', label: 'Value', align: 'right', render: (h) => <span className="num font-semibold">{inr(h.value)}</span>, sort: (h) => h.value },
          { key: 'weight', label: 'Weight', align: 'right', render: (h) => <span className="num">{pct(h.weight)}</span>, sort: (h) => h.weight },
          { key: 'pl', label: 'P&L', align: 'right', render: (h) => <Delta value={h.pl}>{signedInr(h.pl)}</Delta>, sort: (h) => h.pl },
          { key: 'day', label: 'Today', align: 'right', render: (h) => <Delta value={h.daily_pl}>{signedInr(h.daily_pl)}</Delta>, sort: (h) => h.daily_pl },
        ]}
      />
    </Figure>
  )
}
