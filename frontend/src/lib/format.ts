import Decimal from 'decimal.js-light'

/**
 * Formatage fr-FR à partir de chaînes décimales. Aucun calcul ne passe par un nombre flottant :
 * l'arrondi (moitié vers l'extérieur de zéro, comme le backend) se fait en décimal exact.
 */

const DECIMAL_TEXT = /^-?\d+(\.\d+)?$/

function parse(text: string): Decimal {
  if (!DECIMAL_TEXT.test(text)) throw new Error(`Valeur décimale invalide : ${text}`)
  return new Decimal(text)
}

// Intl.NumberFormat accepte une chaîne décimale et la formate sans passer par un flottant.
function format(formatter: Intl.NumberFormat, text: string): string {
  return formatter.format(text as `${number}`)
}

export function formatMoney(amount: string, currency = 'EUR'): string {
  const rounded = parse(amount).toDecimalPlaces(2, Decimal.ROUND_HALF_UP)
  const text = rounded.isZero() ? '0.00' : rounded.toFixed(2)
  return format(new Intl.NumberFormat('fr-FR', { style: 'currency', currency }), text)
}

/** `value` est déjà en pourcents : "12.5" donne "12,50 %". */
export function formatPercent(value: string): string {
  const ratio = parse(value).div(100)
  const formatter = new Intl.NumberFormat('fr-FR', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return format(formatter, ratio.toFixed())
}

export function formatQuantity(value: string): string {
  parse(value)
  const formatter = new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  })
  return format(formatter, value)
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

export function formatDate(isoDate: string): string {
  const match = ISO_DATE.exec(isoDate)
  if (!match) throw new Error(`Date invalide : ${isoDate}`)
  const [, year, month, day] = match.map(Number)
  const date = new Date(Date.UTC(year!, month! - 1, day!))
  if (date.getUTCMonth() !== month! - 1 || date.getUTCDate() !== day) {
    throw new Error(`Date invalide : ${isoDate}`)
  }
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}
