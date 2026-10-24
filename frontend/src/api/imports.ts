import { request } from './client'
import type { ImportCommit, ImportMapping, ImportPreview, ImportResult } from './types'

export interface ImportSettings {
  delimiter: string
  encoding: string
  date_format: string
  decimal_separator: string
}

export interface PreviewParams {
  file: File
  accountId: string
  mappingId?: string
  settings?: ImportSettings
  /** Donnée d'opération → nom de la colonne du fichier. */
  columns?: Record<string, string>
}

/** Analyse le fichier côté serveur sans rien enregistrer. */
export function previewImport(params: PreviewParams): Promise<ImportPreview> {
  const form = new FormData()
  form.set('file', params.file)
  form.set('account_id', params.accountId)
  if (params.mappingId) form.set('mapping_id', params.mappingId)
  if (params.columns && Object.keys(params.columns).length > 0) {
    form.set('columns', JSON.stringify(params.columns))
  }
  if (params.settings) {
    form.set('delimiter', params.settings.delimiter)
    form.set('encoding', params.settings.encoding)
    form.set('date_format', params.settings.date_format)
    form.set('decimal_separator', params.settings.decimal_separator)
  }
  return request<ImportPreview>('POST', '/imports/preview', form)
}

export function commitImport(body: ImportCommit): Promise<ImportResult> {
  return request<ImportResult>('POST', '/imports/commit', body)
}

export function listMappings(): Promise<ImportMapping[]> {
  return request<ImportMapping[]>('GET', '/import-mappings')
}
