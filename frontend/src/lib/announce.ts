import { createContext, useContext } from 'react'

export type Announce = (message: string) => void

export const AnnounceContext = createContext<Announce>(() => {})

/** Annonce un message aux technologies d'assistance (région `aria-live` polie). */
export function useAnnounce(): Announce {
  return useContext(AnnounceContext)
}
