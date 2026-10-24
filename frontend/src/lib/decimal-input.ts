import Decimal from 'decimal.js-light'

const DECIMAL = /^-?\d+(\.\d+)?$/

/**
 * Normalise un nombre saisi à la française ("1 250,50") en chaîne décimale ("1250.50").
 * Renvoie null si le texte n'est pas un nombre décimal simple. Aucun flottant n'intervient.
 */
export function normalizeDecimalInput(text: string): string | null {
  const cleaned = text.replace(/\s/g, '').replace(',', '.')
  return DECIMAL.test(cleaned) ? cleaned : null
}

export function isPositiveDecimal(normalized: string): boolean {
  return new Decimal(normalized).gt(0)
}
