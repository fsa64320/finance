import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '../api/client'
import { suggestTickers, updateInstrument } from '../api/instruments'
import { keys } from '../api/keys'
import { addPrice, listPrices } from '../api/prices'
import type { Instrument, PriceInput, PriceKind, TickerSuggestion } from '../api/types'
import { splitApiError } from '../lib/form-errors'
import { formatDate, formatUnitPrice } from '../lib/format'
import PriceEntryForm from './PriceEntryForm'
import { TextField, buttonClass, secondaryButtonClass } from './fields'

const KIND_LABELS: Record<PriceKind, string> = {
  MARKET: 'Cours',
  NAV: 'Valeur liquidative',
  SUBSCRIPTION: 'Prix de souscription',
  REDEMPTION: 'Prix de retrait',
}
const PRICED = new Set<Instrument['kind']>(['EQUITY', 'ETF', 'FUND', 'FCPE', 'SCPI'])
const WITH_TICKER = new Set<Instrument['kind']>(['EQUITY', 'ETF', 'FUND', 'FCPE'])
const LATEST_SHOWN = 5

interface InstrumentPanelProps {
  instrument: Instrument
  onClose: () => void
}

/** Ticker de cotation, suggestions OpenFIGI et prix saisis ou récupérés pour un actif. */
export default function InstrumentPanel({ instrument, onClose }: InstrumentPanelProps) {
  const queryClient = useQueryClient()
  const [ticker, setTicker] = useState(instrument.price_ticker ?? '')
  const [suggestions, setSuggestions] = useState<TickerSuggestion[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [disabledSource, setDisabledSource] = useState(false)

  const prices = useQuery({
    queryKey: keys.prices(instrument.id),
    queryFn: () => listPrices(instrument.id),
    enabled: PRICED.has(instrument.kind),
  })

  const save = useMutation({
    mutationFn: (value: string) => updateInstrument(instrument.id, { price_ticker: value }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.instruments }),
    onError: (failure) => setProblem(splitApiError(failure, []).general),
  })

  const search = useMutation({
    mutationFn: () => suggestTickers(instrument.id),
    onSuccess: (found) => {
      setProblem(null)
      setDisabledSource(false)
      setSuggestions(found)
    },
    onError: (failure) => {
      setSuggestions(null)
      setDisabledSource(failure instanceof ApiError && failure.status === 409)
      setProblem(splitApiError(failure, []).general)
    },
  })

  async function enterPrices(inputs: PriceInput[]) {
    for (const input of inputs) await addPrice(input)
    await Promise.all(
      [keys.prices(instrument.id), keys.dashboard, keys.accounts].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    )
  }

  const latest = [...(prices.data ?? [])]
    .sort((a, b) => b.price_date.localeCompare(a.price_date))
    .slice(0, LATEST_SHOWN)

  return (
    <section
      aria-label={`Gestion de ${instrument.name}`}
      className="mt-8 rounded-2xl border border-line bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-medium">{instrument.name}</h3>
        <button type="button" className={secondaryButtonClass} onClick={onClose}>
          Fermer
        </button>
      </div>

      {problem && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {problem}{' '}
          {disabledSource && (
            <Link className="text-brand underline" to="/reglages">
              Activer dans les réglages
            </Link>
          )}
        </p>
      )}

      {WITH_TICKER.has(instrument.kind) && (
        <div className="mt-4 max-w-md">
          <TextField
            id={`ticker-${instrument.id}`}
            label="Ticker de cotation de cet actif"
            value={ticker}
            onChange={setTicker}
            hint="Sert à récupérer les cours si la récupération automatique est activée."
          />
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              className={buttonClass}
              disabled={save.isPending}
              onClick={() => save.mutate(ticker.trim())}
            >
              Enregistrer le ticker
            </button>
            {instrument.isin && (
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={search.isPending}
                onClick={() => search.mutate()}
              >
                Chercher un ticker
              </button>
            )}
          </div>
          {suggestions !== null && suggestions.length === 0 && (
            <p className="mt-3 text-sm text-muted">Aucun ticker trouvé pour cet ISIN.</p>
          )}
          {suggestions !== null && suggestions.length > 0 && (
            <ul className="mt-3 space-y-2 text-sm">
              {suggestions.map((item) => (
                <li key={`${item.ticker}-${item.exchange}`} className="flex items-center gap-3">
                  <span>
                    {item.ticker} — {item.name} ({item.exchange})
                  </span>
                  <button
                    type="button"
                    className={secondaryButtonClass}
                    onClick={() => {
                      setTicker(item.ticker)
                      save.mutate(item.ticker)
                    }}
                  >
                    Utiliser {item.ticker}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {PRICED.has(instrument.kind) ? (
        <div className="mt-6">
          <h4 className="font-medium">Prix</h4>
          {latest.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table aria-label="Derniers prix" className="w-full text-left text-sm">
                <thead className="text-muted">
                  <tr>
                    <th scope="col" className="py-2 pr-4 font-medium">
                      Date
                    </th>
                    <th scope="col" className="py-2 pr-4 font-medium">
                      Sorte
                    </th>
                    <th scope="col" className="py-2 pr-4 font-medium">
                      Valeur
                    </th>
                    <th scope="col" className="py-2 font-medium">
                      Origine
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {latest.map((price) => (
                    <tr
                      key={`${price.kind}-${price.price_date}-${price.source}`}
                      className="border-t border-line"
                    >
                      <td className="py-2 pr-4">{formatDate(price.price_date)}</td>
                      <td className="py-2 pr-4">{KIND_LABELS[price.kind]}</td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        {formatUnitPrice(price.value, price.currency)}
                      </td>
                      <td className="py-2">
                        {price.source === 'MANUAL' ? 'Saisi' : 'Automatique'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 max-w-md">
            <PriceEntryForm instrument={instrument} onSubmit={enterPrices} />
          </div>
        </div>
      ) : (
        <p className="mt-6 text-muted">
          Cet actif se valorise par un solde déclaré, pas par un prix : déclarez le solde depuis la
          page du compte.
        </p>
      )}
    </section>
  )
}
