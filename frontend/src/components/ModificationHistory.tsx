import type { Transaction } from '../api/types'
import { formatDate, formatMoney, formatQuantity } from '../lib/format'

function createdOn(version: Transaction): string {
  return version.created_at ? formatDate(version.created_at.slice(0, 10)) : ''
}

/** Historique d'une opération : une ligne par version, de la plus récente à la plus ancienne. */
export default function ModificationHistory({ versions }: { versions: Transaction[] }) {
  const ordered = [...versions].sort((a, b) => b.version - a.version)
  return (
    <div className="mt-2">
      {versions.length <= 1 && (
        <p className="text-sm text-muted">
          Aucune modification : cette opération n'a qu'une version.
        </p>
      )}
      <table aria-label="Historique des modifications" className="mt-2 w-full text-left text-sm">
        <thead className="text-muted">
          <tr>
            <th className="py-1 pr-3 font-medium">Version</th>
            <th className="py-1 pr-3 font-medium">Date</th>
            <th className="py-1 pr-3 font-medium">Quantité</th>
            <th className="py-1 pr-3 font-medium">Effet sur la trésorerie</th>
            <th className="py-1 font-medium">Statut</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((version) => (
            <tr key={version.version} className="border-t border-line">
              <td className="py-1 pr-3">Version {version.version}</td>
              <td className="py-1 pr-3">{createdOn(version)}</td>
              <td className="py-1 pr-3">
                {version.quantity ? formatQuantity(version.quantity) : '—'}
              </td>
              <td className="py-1 pr-3">{formatMoney(version.cash_amount, version.currency)}</td>
              <td className="py-1">{version.voided ? 'Annulée' : 'En vigueur'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
