/** Raisons d'une valeur estimée ou périmée (FR-025), nommées pour ne pas reposer sur la couleur. */
const LABELS: Record<string, string> = {
  price_stale: 'prix ancien',
  rate_stale: 'taux ancien',
  rate_missing: 'taux manquant',
  declared_balance_missing: 'solde non déclaré',
  non_convertible: 'non convertible',
}

interface StaleBadgeProps {
  /** Code de l'avertissement du serveur ; sans lui, la pastille dit simplement « estimé ». */
  code?: string
  label?: string
}

export default function StaleBadge({ code, label }: StaleBadgeProps) {
  return (
    <span className="rounded bg-warn-bg px-1.5 py-0.5 text-xs text-warn-ink">
      {label ?? (code ? LABELS[code] : undefined) ?? 'estimé'}
    </span>
  )
}
