import { useEffect, useState } from 'react'

type Health = { status: string; version: string; env: string }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-2xl font-semibold">Portfolio Intelligence</h1>
      <p className="mt-1 text-sm text-slate-400">
        Academic decision-support system. Not financial advice.
      </p>
      <section className="mt-8 max-w-sm rounded-lg border border-slate-800 p-4">
        <h2 className="text-sm text-slate-400">Backend</h2>
        {health && (
          <p className="mt-1 text-emerald-400">
            {health.status} · v{health.version} · {health.env}
          </p>
        )}
        {error && <p className="mt-1 text-red-400">unreachable ({error})</p>}
        {!health && !error && <p className="mt-1 text-slate-500">checking…</p>}
      </section>
    </main>
  )
}
