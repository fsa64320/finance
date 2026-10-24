import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { addLivretRate, listLivretRates } from '../api/rates'
import { getSettings, patchSettings } from '../api/settings'
import { keys } from '../api/keys'
import type { LivretARate } from '../api/types'
import LivretARatesEditor from '../components/LivretARatesEditor'
import PriceFetchConsent from '../components/PriceFetchConsent'

const cardClass = 'rounded-2xl border border-line bg-card p-5 shadow-sm'

export default function Settings() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: keys.settings, queryFn: getSettings })
  const rates = useQuery({ queryKey: keys.livretRates, queryFn: listLivretRates })

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => patchSettings({ auto_fetch_prices: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.settings }),
  })
  const add = useMutation({
    mutationFn: (rate: LivretARate) => addLivretRate(rate),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.livretRates })
      await queryClient.invalidateQueries({ queryKey: keys.dashboard })
      await queryClient.invalidateQueries({ queryKey: keys.accounts })
    },
  })

  return (
    <section>
      <h2 className="text-xl font-semibold">Réglages</h2>

      <div className={`${cardClass} mt-4`}>
        <h3 className="font-medium">Cours et taux automatiques</h3>
        {settings.isPending && <p className="mt-2 text-muted">Chargement…</p>}
        {settings.isError && (
          <p role="alert" className="mt-2 text-danger">
            Impossible de charger les réglages.
          </p>
        )}
        {settings.data && (
          <div className="mt-2">
            <PriceFetchConsent
              settings={settings.data}
              onChange={(enabled) => toggle.mutateAsync(enabled)}
            />
            {toggle.isError && (
              <p role="alert" className="mt-3 text-danger">
                Impossible d’enregistrer ce choix.
              </p>
            )}
          </div>
        )}
      </div>

      <div className={`${cardClass} mt-6`}>
        <h3 className="font-medium">Taux du Livret A</h3>
        {rates.isPending && <p className="mt-2 text-muted">Chargement…</p>}
        {rates.isError && (
          <p role="alert" className="mt-2 text-danger">
            Impossible de charger les taux.
          </p>
        )}
        {rates.data && (
          <div className="mt-2">
            <LivretARatesEditor rates={rates.data} onAdd={(rate) => add.mutateAsync(rate)} />
          </div>
        )}
      </div>
    </section>
  )
}
