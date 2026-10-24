import { useCallback, useState, type ReactNode } from 'react'

import { AnnounceContext } from '../lib/announce'

/** Fournit une région `aria-live` pour annoncer succès, fins d'import et expirations de session. */
export default function LiveAnnouncer({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState('')
  const announce = useCallback((next: string) => setMessage(next), [])
  return (
    <AnnounceContext.Provider value={announce}>
      {children}
      <div role="status" aria-live="polite" className="sr-only">
        {message}
      </div>
    </AnnounceContext.Provider>
  )
}
