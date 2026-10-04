// Display formatting: Indian digit grouping, true minus signs, percentages and points.
const inrFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const inr2Fmt = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const MINUS = '−'

export const inr = (v: number) => (v < 0 ? MINUS : '') + `₹${inrFmt.format(Math.abs(v))}`
export const inr2 = (v: number) => `₹${inr2Fmt.format(v)}`
export const signedInr = (v: number) => (v > 0 ? '+' : v < 0 ? MINUS : '') + `₹${inrFmt.format(Math.abs(v))}`
export const pct = (v: number, d = 1) => `${(v * 100).toFixed(d).replace('-', MINUS)}%`
export const signedPct = (v: number, d = 1) => (v > 0 ? '+' : '') + pct(v, d)
export const pts = (v: number, d = 1) => `${v > 0 ? '+' : v < 0 ? MINUS : ''}${Math.abs(v * 100).toFixed(d)} pts`
export const fixed = (v: number, d = 2) => v.toFixed(d).replace('-', MINUS)
export const signed = (v: number, d = 2) => (v > 0 ? '+' : '') + fixed(v, d)
export const day = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
