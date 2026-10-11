// Sign-in (Phase 17): Cognito managed login, authorization code + PKCE, no SDK.
// Off when VITE_COGNITO_DOMAIN / VITE_COGNITO_CLIENT_ID are unset, i.e. in local development.
// API Gateway's JWT authorizer verifies the access token; the app never trusts it on its own.

const domain = import.meta.env.VITE_COGNITO_DOMAIN as string | undefined // https://<prefix>.auth.<region>.amazoncognito.com
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined
export const authEnabled = Boolean(domain && clientId)

type Tokens = { access: string; refresh?: string; expires: number }
const KEY = 'pi-auth'
const PKCE = 'pi-pkce'
const RETURN = 'pi-return'
const redirectUri = () => `${location.origin}/`

// sessionStorage: tokens end with the tab, and never reach other origins. Wrapped because private modes can throw.
const read = (k: string) => {
  try {
    return sessionStorage.getItem(k)
  } catch {
    return null
  }
}
const write = (k: string, v: string | null) => {
  try {
    if (v === null) sessionStorage.removeItem(k)
    else sessionStorage.setItem(k, v)
  } catch {
    /* unavailable: the user signs in again next time */
  }
}
const load = (): Tokens | null => JSON.parse(read(KEY) ?? 'null')

const b64url = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const random = () => b64url(crypto.getRandomValues(new Uint8Array(32)))

async function tokenRequest(body: Record<string, string>): Promise<Tokens> {
  const r = await fetch(`${domain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: clientId!, ...body }),
  })
  if (!r.ok) throw new Error(`token request failed (HTTP ${r.status})`)
  const j = await r.json()
  // A refresh response carries no new refresh token: keep the old one.
  const t = { access: j.access_token, refresh: j.refresh_token ?? load()?.refresh, expires: Date.now() + j.expires_in * 1000 }
  write(KEY, JSON.stringify(t))
  return t
}

export async function signIn(): Promise<void> {
  const verifier = random()
  const state = random()
  const challenge = b64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))))
  write(PKCE, JSON.stringify({ verifier, state }))
  write(RETURN, location.hash) // come back to the same page
  const q = new URLSearchParams({
    response_type: 'code',
    client_id: clientId!,
    redirect_uri: redirectUri(),
    scope: 'openid email',
    code_challenge_method: 'S256',
    code_challenge: challenge,
    state,
  })
  location.assign(`${domain}/oauth2/authorize?${q}`)
}

export function signOut(): void {
  write(KEY, null)
  location.assign(`${domain}/logout?${new URLSearchParams({ client_id: clientId!, logout_uri: redirectUri() })}`)
}

/** A valid access token, refreshed when it is about to expire; null when signed out or auth is off. */
export async function accessToken(): Promise<string | null> {
  if (!authEnabled) return null
  const t = load()
  if (t && t.expires - 60_000 > Date.now()) return t.access
  if (t?.refresh) {
    try {
      return (await tokenRequest({ grant_type: 'refresh_token', refresh_token: t.refresh })).access
    } catch {
      write(KEY, null)
    }
  }
  return null
}

/** Run before the first render. True: render the app. False: the browser is on its way to the login page. */
export async function ensureSignedIn(): Promise<boolean> {
  if (!authEnabled) return true
  // The phone hand-off link carries a single-use import token instead of a login.
  if (location.hash.startsWith('#/import/')) return true
  const q = new URLSearchParams(location.search)
  const code = q.get('code')
  if (code) {
    const pkce = JSON.parse(read(PKCE) ?? 'null') as { verifier: string; state: string } | null
    write(PKCE, null)
    history.replaceState(null, '', `/${read(RETURN) ?? ''}`)
    if (pkce && pkce.state === q.get('state')) {
      await tokenRequest({ grant_type: 'authorization_code', code, code_verifier: pkce.verifier, redirect_uri: redirectUri() })
      return true
    }
  }
  if (await accessToken()) return true
  await signIn()
  return false
}
