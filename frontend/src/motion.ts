import { flushSync } from 'react-dom'

/** A valid view-transition-name fragment from any key. */
export const slug = (s: string) => s.replace(/[^a-zA-Z0-9_-]+/g, '_')

/** Apply a state change with elements sliding to their new place where View Transitions exist. */
export function reorder(update: () => void) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!document.startViewTransition || reduce) return update()
  document.startViewTransition(() => flushSync(update))
}
