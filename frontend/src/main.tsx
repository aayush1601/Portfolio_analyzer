import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ensureSignedIn } from './auth'

const root = createRoot(document.getElementById('root')!)
ensureSignedIn()
  .then((ok) => {
    if (ok)
      root.render(
        <StrictMode>
          <App />
        </StrictMode>,
      )
  })
  .catch(() =>
    root.render(
      <p style={{ padding: 24, fontFamily: 'system-ui' }}>
        Sign-in didn’t complete. <a href="/">Try again</a>.
      </p>,
    ),
  )
