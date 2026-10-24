import { useState } from 'react'

import type { Settings } from '../api/types'
import { buttonClass, secondaryButtonClass } from './fields'

interface PriceFetchConsentProps {
  settings: Pick<Settings, 'auto_fetch_prices' | 'external_services'>
  onChange: (enabled: boolean) => Promise<unknown>
}

/**
 * Choix explicite de la récupération automatique des cours (FR-029). Désactivée par défaut : tant
 * que la personne ne l'a pas activée, rien ne sort. La liste des services et des données envoyées
 * est toujours visible, pour décider en connaissance de cause.
 */
export default function PriceFetchConsent({ settings, onChange }: PriceFetchConsentProps) {
  const [pending, setPending] = useState(false)
  const enabled = settings.auto_fetch_prices

  async function toggle() {
    setPending(true)
    try {
      await onChange(!enabled)
    } finally {
      setPending(false)
    }
  }

  return (
    <div>
      <p role="status" className="font-medium">
        {enabled
          ? 'Récupération automatique activée : les services ci-dessous sont contactés quand vous mettez à jour les cours.'
          : 'Récupération automatique désactivée : rien ne sort de votre ordinateur. Saisissez les prix à la main, ou activez la récupération.'}
      </p>
      <p className="mt-2 text-sm text-muted">
        Vos comptes, quantités, montants et dates d’opération ne sont jamais envoyés. Seuls des
        identifiants d’actifs (ticker, ISIN) et des devises sortent.
      </p>
      <ul aria-label="Services contactés" className="mt-3 space-y-3 text-sm">
        {settings.external_services.map((service) => (
          <li key={service.name} className="rounded-lg border border-line p-3">
            <p className="font-medium">{service.name}</p>
            <p className="text-muted">{service.purpose}</p>
            <p className="mt-1">
              <span className="font-medium">Données envoyées : </span>
              {service.data_sent}
            </p>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className={`${enabled ? secondaryButtonClass : buttonClass} mt-4`}
        disabled={pending}
        onClick={() => void toggle()}
      >
        {pending
          ? 'Enregistrement…'
          : enabled
            ? 'Désactiver la récupération automatique'
            : 'Activer la récupération automatique'}
      </button>
    </div>
  )
}
