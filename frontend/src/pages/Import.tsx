import { useEffect, useState } from 'react'
import { Riskometer } from '../charts'
import { ApiError, useApi, type Risk } from '../api'
import { inr, pct, signedInr } from '../format'
import { Avatar, Button, Card, Chip, IconArrow, Notes, Status } from '../ui'

type ImportResult = {
  portfolio_id: string
  statement_to: string
  funds: { scheme_code: string; name: string; units: number; value: number; cost: number | null; in_universe: boolean }[]
  skipped: string[]
  notes: string[]
}
type Session = { token: string; phone_url: string; qr_svg: string; expires_in: number }

const field =
  'w-full rounded-lg border border-line bg-panel px-3 py-2 text-[0.9rem] font-medium text-ink hover:border-ink-3 focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40'

async function upload(form: FormData): Promise<ImportResult> {
  const r = await fetch('/api/import', { method: 'POST', body: form })
  const body = await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(typeof body?.detail === 'string' ? body.detail : `Import failed (HTTP ${r.status})`)
  return body
}

/** The CAS upload form; used on the laptop and on the phone. */
function UploadForm({ token, onDone }: { token: string; onDone: (r: ImportResult) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return setError('Choose your CAS PDF first.')
    setError(null)
    setBusy(true)
    const form = new FormData()
    form.append('file', file)
    form.append('password', password.trim().toUpperCase())
    form.append('token', token)
    if (name.trim()) form.append('name', name.trim())
    try {
      onDone(await upload(form))
      setPassword('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-[0.85rem] font-bold text-ink-2">CAS PDF</span>
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-[0.88rem] text-ink-2 file:mr-3 file:rounded-lg file:border-0 file:bg-accent-soft file:px-3 file:py-2 file:font-bold file:text-accent-ink hover:file:bg-accent hover:file:text-white"
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[0.85rem] font-bold text-ink-2">PDF password</span>
        <input
          type="password"
          autoComplete="off"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Your PAN, e.g. ABCDE1234F"
          className={field}
        />
        <span className="mt-1 block text-[0.78rem] text-ink-3">Used once to open the file, never stored.</span>
      </label>
      <label className="block">
        <span className="mb-1 block text-[0.85rem] font-bold text-ink-2">Portfolio name (optional)</span>
        <input value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="Imported funds" className={field} />
      </label>
      {error && (
        <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-[0.9rem] text-loss">
          {error}
        </p>
      )}
      <Button variant="primary" type="submit" disabled={busy} className="w-full sm:w-auto">
        {busy ? 'Reading your statement…' : 'Import funds'}
      </Button>
    </form>
  )
}

function RiskSummary({ pid }: { pid: string }) {
  const q = useApi<Risk>(`/portfolio/${pid}/risk`)
  return (
    <Status q={q} what="the risk rating">
      {(r) => {
        const year = r.holding_periods.find((h) => h.days === 252)
        return (
          <div className="grid items-center gap-5 sm:grid-cols-[220px_minmax(0,1fr)]">
            <div className="text-center">
              <Riskometer score={r.risk_score} band={r.risk_band} />
              <p className="mt-1 text-[0.9rem] font-bold text-ink">
                {r.risk_band} risk · {r.risk_score} of 100
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[0.9rem]">
              <div>
                <dt className="text-[0.8rem] text-ink-3">Volatility</dt>
                <dd className="num font-bold">{pct(r.volatility_ann)} a year</dd>
              </div>
              <div>
                <dt className="text-[0.8rem] text-ink-3">Worst fall (5 years)</dt>
                <dd className="num font-bold text-loss">{pct(r.score_drawdown)}</dd>
              </div>
              <div>
                <dt className="text-[0.8rem] text-ink-3">Bad day (1 in 20)</dt>
                <dd className="num font-bold">{pct(-r.var_1d.historical)}</dd>
              </div>
              {year && (
                <div>
                  <dt className="text-[0.8rem] text-ink-3">Chance of a loss over 1 year</dt>
                  <dd className="num font-bold">{pct(year.prob_loss, 0)}</dd>
                </div>
              )}
            </dl>
          </div>
        )
      }}
    </Status>
  )
}

function Result({ r, onImported }: { r: ImportResult; onImported: () => void }) {
  useEffect(onImported, [r.portfolio_id, onImported])
  const total = r.funds.reduce((a, f) => a + f.value, 0)
  const cost = r.funds.reduce((a, f) => a + (f.cost ?? f.value), 0)
  const outside = r.funds.filter((f) => !f.in_universe).length
  return (
    <div className="grid gap-5">
      <Card
        title={`Found ${r.funds.length} fund${r.funds.length === 1 ? '' : 's'} worth ${inr(total)}${r.statement_to ? ` on ${r.statement_to}` : ''}.`}
        dek={`${signedInr(total - cost)} on what they cost.${outside ? ` ${outside} ${outside === 1 ? 'is' : 'are'} outside the research universe: valued and risk-rated, but not yet opened up for look-through.` : ''}`}
        source={r.notes.length || r.skipped.length ? <Notes notes={[...r.notes, ...r.skipped.map((s) => `Skipped (no AMFI code in the statement): ${s}`)]} /> : undefined}
      >
        <ul className="-mx-5 divide-y divide-line-soft border-t border-line sm:-mx-6">
          {r.funds.map((f) => (
            <li key={f.scheme_code} className="flex items-center gap-3 px-5 py-3 sm:px-6">
              <Avatar id={f.scheme_code} label={f.name} />
              <div className="min-w-0 flex-1">
                <p className="font-bold text-ink">{f.name}</p>
                <p className="text-[0.8rem] text-ink-3">
                  {f.units.toLocaleString('en-IN', { maximumFractionDigits: 3 })} units {!f.in_universe && <Chip>Outside research universe</Chip>}
                </p>
              </div>
              <p className="num text-right font-bold">{inr(f.value)}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Risk rating of the imported funds" dek="Computed from today’s mix over the last year, with the worst fall measured over five years.">
        <RiskSummary pid={r.portfolio_id} />
        <div className="mt-5 flex flex-wrap gap-2 border-t border-line-soft pt-4">
          <a href={`#/overview/${r.portfolio_id}`} className="no-underline">
            <Button variant="primary">
              Open the portfolio <IconArrow className="size-3.5" />
            </Button>
          </a>
          <a href={`#/risk/${r.portfolio_id}`} className="no-underline">
            <Button>Full risk view</Button>
          </a>
        </div>
      </Card>
    </div>
  )
}

const HOW = (
  <ol className="space-y-2 text-[0.9rem] text-ink-2">
    <li>
      <span className="font-bold text-ink">1. Get your CAS.</span> Request a detailed Consolidated Account Statement from CAMS, KFintech or MF Central. It
      arrives by email as a PDF and covers every fund house you invest with.
    </li>
    <li>
      <span className="font-bold text-ink">2. Upload it here</span> with its password, which is your PAN in capital letters.
    </li>
    <li>
      <span className="font-bold text-ink">3. See your funds and their risk.</span> The statement is read in memory; the PDF and PAN are never stored, only each
      fund’s units and cost.
    </li>
  </ol>
)

/** Phone view, opened from the QR code: just the form, then a short confirmation. */
export function PhoneImport({ token }: { token: string }) {
  const [done, setDone] = useState<ImportResult | null>(null)
  const noop = () => {}
  return (
    <div className="mx-auto max-w-lg">
      <Card title={done ? 'Imported. Your laptop now shows the result.' : 'Upload your CAS from this phone'} dek={done ? undefined : 'Pick the PDF from your email or files.'}>
        {done ? <Result r={done} onImported={noop} /> : <UploadForm token={token} onDone={setDone} />}
      </Card>
    </div>
  )
}

/** Laptop view: upload here, or scan the QR to upload from the phone; either way the result appears here. */
export function ImportPage({ onImported }: { onImported: () => void }) {
  const [session, setSession] = useState<Session | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [phonePid, setPhonePid] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/import/session?port=${window.location.port || 80}`, { method: 'POST' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setSession)
      .catch((e: Error) => setSessionError(e.message))
  }, [])

  // Watch for an upload from the phone.
  useEffect(() => {
    if (!session || result || phonePid) return
    const id = window.setInterval(async () => {
      const s = await fetch(`/api/import/session/${session.token}`).then((r) => r.json()).catch(() => null)
      if (s?.portfolio_id) setPhonePid(s.portfolio_id)
    }, 2000)
    return () => window.clearInterval(id)
  }, [session, result, phonePid])

  if (result) return <Result r={result} onImported={onImported} />
  if (phonePid)
    return (
      <Card title="Your phone finished the import." dek="Here is the risk rating of the funds it found.">
        <ImportedFromPhone pid={phonePid} onImported={onImported} />
      </Card>
    )

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
      <Card title="Import your mutual funds from every fund house" dek="One statement, every folio: the same Consolidated Account Statement other investing apps use.">
        {HOW}
        <div className="mt-5 border-t border-line-soft pt-5">
          {session ? (
            <UploadForm token={session.token} onDone={setResult} />
          ) : (
            <p className="text-ink-3">{sessionError ? `Couldn’t start an import: ${sessionError}` : 'Preparing a secure upload…'}</p>
          )}
        </div>
      </Card>
      <Card title="Or upload from your phone" dek="Scan with your phone camera. The phone must be on the same Wi-Fi as this laptop.">
        {session ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-56 max-w-full rounded-xl border border-line p-2 [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: session.qr_svg }} />
            <p className="text-center text-[0.8rem] text-ink-3">
              Waiting for your phone… This code works for {Math.round(session.expires_in / 60)} minutes.
              <span className="mt-1 block break-all">{session.phone_url}</span>
            </p>
          </div>
        ) : (
          <p className="text-ink-3">Preparing the QR code…</p>
        )}
      </Card>
    </div>
  )
}

function ImportedFromPhone({ pid, onImported }: { pid: string; onImported: () => void }) {
  useEffect(onImported, [pid, onImported])
  return (
    <>
      <RiskSummary pid={pid} />
      <div className="mt-5 flex flex-wrap gap-2 border-t border-line-soft pt-4">
        <a href={`#/overview/${pid}`} className="no-underline">
          <Button variant="primary">
            Open the portfolio <IconArrow className="size-3.5" />
          </Button>
        </a>
      </div>
    </>
  )
}
