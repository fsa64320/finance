/** Graduations lisibles des axes du graphique d'évolution. */

const DAY = 24 * 60 * 60 * 1000

export function spanInDays(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY)
}

/** Jour/mois sur une période de quatre mois ou moins, mois/année au-delà. */
export function formatTickDate(iso: string, spanDays: number): string {
  const [year, month, day] = iso.split('-')
  return spanDays <= 120 ? `${day}/${month}` : `${month}/${year?.slice(2)}`
}

/** Montant arrondi à l'euro : assez court pour l'axe, sans tronquer la valeur. */
export function formatTickMoney(value: number, currency: string): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
    useGrouping: 'always',
  }).format(value)
}
