import { useState } from 'react'
import type { AssetType, Holding, Reference } from '../api'
import { Button, IconPlus, IconTrash } from '../ui'

const field =
  'w-full rounded-lg border border-line bg-panel px-3 py-2 text-[0.9rem] font-medium text-ink hover:border-ink-3 focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40'

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
          <span className="mb-1 block text-[0.85rem] font-bold text-ink-2">Portfolio name</span>
          <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={field} placeholder="e.g. Retirement" />
        </label>
      )}
      <div className="-mx-5 overflow-x-auto sm:-mx-6">
        <table className="w-full min-w-[640px] text-[0.9rem]">
          <caption className="sr-only">Editable holdings</caption>
          <thead>
            <tr className="border-b border-line text-left text-[0.78rem] text-ink-3">
              <th scope="col" className="w-32 py-2.5 pr-2 pl-5 font-bold sm:pl-6">Type</th>
              <th scope="col" className="py-2.5 pr-2 font-bold">Asset</th>
              <th scope="col" className="w-36 py-2.5 pr-2 font-bold">Quantity / units</th>
              <th scope="col" className="w-40 py-2.5 pr-2 font-bold">Avg cost per unit (₹)</th>
              <th scope="col" className="w-12 py-2.5 pr-5 sm:pr-6"><span className="sr-only">Remove</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-line-soft">
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
                    <option value="MF">Mutual fund</option>
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
                    className={`${field} num disabled:bg-canvas disabled:text-ink-3`}
                    value={r.avg_cost}
                    placeholder={r.asset_type === 'CASH' ? 'n/a' : ''}
                    onChange={(e) => set(i, { avg_cost: e.target.value })}
                  />
                </td>
                <td className="py-2 pr-5 text-right sm:pr-6">
                  <button type="button" aria-label={`Remove row ${i + 1}`} className="rounded-md p-1.5 text-ink-3 hover:bg-loss-soft hover:text-loss" onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>
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
        <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-loss">
          {error}
        </p>
      )}
      <div className="flex gap-2 border-t border-line-soft pt-4">
        <Button variant="primary" type="submit" disabled={saving || rows.length === 0}>
          {saving ? 'Saving…' : withName ? 'Create portfolio' : 'Save holdings'}
        </Button>
        <Button type="button" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
