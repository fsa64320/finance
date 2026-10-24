import { request } from './client'

/** Export complet (JSON non chiffré) ; sa structure est décrite dans contracts/export-format.md. */
export type ExportFile = Record<string, unknown>

export function exportData(): Promise<ExportFile> {
  return request<ExportFile>('GET', '/data/export')
}

/** Restaure un export dans une instance vide ; le fichier est transmis tel quel. */
export function restoreData(payload: ExportFile): Promise<void> {
  return request<void>('POST', '/data/restore', payload)
}
