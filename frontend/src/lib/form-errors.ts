import { ApiError } from '../api/client'

export interface FormErrors {
  fields: Record<string, string>
  general: string | null
}

/**
 * Répartit une erreur d'API entre les champs du formulaire et un message général.
 * `aliases` rattache les noms de champs du serveur à ceux du formulaire (instrument → instrument_id).
 */
export function splitApiError(
  failure: unknown,
  knownFields: readonly string[],
  aliases: Record<string, string> = {},
): FormErrors {
  if (!(failure instanceof ApiError)) {
    return { fields: {}, general: 'Une erreur inattendue est survenue.' }
  }
  const fields: Record<string, string> = {}
  const unplaced: string[] = []
  for (const detail of failure.details ?? []) {
    const target = aliases[detail.field] ?? detail.field
    if (knownFields.includes(target)) fields[target] = detail.message
    else unplaced.push(detail.message)
  }
  if (Object.keys(fields).length === 0 && unplaced.length === 0) {
    return { fields, general: failure.message }
  }
  return { fields, general: unplaced.length > 0 ? unplaced.join(' ') : null }
}
