import { Link } from 'react-router-dom'

import type { AccountSummary } from '../api/types'
import { formatDate, formatMoney } from '../lib/format'
import { ACCOUNT_TYPE_LABELS } from '../lib/labels'

interface AccountListProps {
  accounts: AccountSummary[]
  /** Nom accessible du tableau. */
  label?: string
  /** Ajoute la colonne Statut (ouvert ou clos). */
  showStatus?: boolean
}

/** Tableau des comptes : le conteneur défile au lieu de déborder de l'écran sur téléphone. */
export default function AccountList({
  accounts,
  label = 'Comptes',
  showStatus = false,
}: AccountListProps) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full text-left text-sm">
        <thead className="text-muted">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">
              Compte
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Type
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Établissement
            </th>
            <th scope="col" className="py-2 pr-4 text-right tabular-nums font-medium">
              Valeur
            </th>
            {showStatus && (
              <th scope="col" className="py-2 font-medium">
                Statut
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.id} className="border-t border-line">
              <td className="py-2 pr-4 font-medium">
                <Link className="text-brand underline" to={`/comptes/${account.id}`}>
                  {account.name}
                </Link>
              </td>
              <td className="py-2 pr-4">{ACCOUNT_TYPE_LABELS[account.type]}</td>
              <td className="py-2 pr-4">{account.institution ?? '—'}</td>
              <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
                <span>{formatMoney(account.value, account.currency)}</span>{' '}
                {account.estimated && (
                  <span className="rounded bg-warn-bg px-1.5 py-0.5 text-xs text-warn-ink">
                    Estimé
                  </span>
                )}
              </td>
              {showStatus && (
                <td className="py-2">
                  {account.closed_on ? `Clos le ${formatDate(account.closed_on)}` : 'Ouvert'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
