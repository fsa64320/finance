import type { ImportCommit, InstrumentKind } from '../api/types'

export interface UnknownInstrument {
  key: string
  name: string
  isin?: string | null
  rows?: number
}

/** Décision prise pour un actif inconnu du fichier. */
export interface Choice {
  action: 'create' | 'link' | 'skip'
  kind?: InstrumentKind
  instrumentId?: string
}

type Resolution = NonNullable<ImportCommit['instrument_resolutions']>[number]

/** Une décision est complète quand elle porte ce que son action demande. */
export function isResolved(choice: Choice | undefined): boolean {
  if (choice === undefined) return false
  if (choice.action === 'create') return choice.kind !== undefined
  if (choice.action === 'link') return choice.instrumentId !== undefined
  return true
}

export function toResolutions(
  items: UnknownInstrument[],
  choices: Record<string, Choice>,
): Resolution[] {
  const resolutions: Resolution[] = []
  for (const item of items) {
    const choice = choices[item.key]
    if (choice === undefined) continue
    if (choice.action === 'create') {
      resolutions.push({ key: item.key, action: 'create', kind: choice.kind })
    } else if (choice.action === 'link') {
      resolutions.push({ key: item.key, action: 'link', instrument_id: choice.instrumentId })
    } else {
      resolutions.push({ key: item.key, action: 'skip' })
    }
  }
  return resolutions
}
