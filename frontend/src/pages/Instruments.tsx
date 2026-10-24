import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { Link } from 'react-router-dom'

import { createInstrument, listInstruments } from '../api/instruments'
import { keys } from '../api/keys'
import { refreshPrices } from '../api/prices'
import type { Instrument, InstrumentInput, InstrumentKind, RefreshSource } from '../api/types'
import ErrorState from '../components/ErrorState'
import InstrumentPanel from '../components/InstrumentPanel'
import LoadingState from '../components/LoadingState'
import { SelectField, TextField, buttonClass, secondaryButtonClass } from '../components/fields'
import { useAnnounce } from '../lib/announce'
import { splitApiError } from '../lib/form-errors'
import { INSTRUMENT_KIND_LABELS, PRICE_MODE_LABELS } from '../lib/labels'

const SOURCE_NAMES: Record<string, string> = { ecb: 'BCE', yahoo: 'Yahoo Finance' }
const ISIN_SHAPE = /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/
const FIELDS = ['kind', 'name', 'isin', 'currency', 'price_ticker'] as const
const KIND_OPTIONS = (Object.keys(INSTRUMENT_KIND_LABELS) as InstrumentKind[]).map((kind) => ({
  value: kind,
  label: INSTRUMENT_KIND_LABELS[kind],
}))

export default function Instruments() {
  const queryClient = useQueryClient()
  const announce = useAnnounce()
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: listInstruments })

  const [kind, setKind] = useState<InstrumentKind>('ETF')
  const [name, setName] = useState('')
  const [isin, setIsin] = useState('')
  const [currency, setCurrency] = useState('EUR')
  const [ticker, setTicker] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [managedId, setManagedId] = useState<string | null>(null)

  const refresh = useMutation({
    mutationFn: () => refreshPrices(),
    onSuccess: async () => {
      await Promise.all(
        [keys.dashboard, keys.accounts, keys.instruments].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      )
    },
  })

  const create = useMutation({
    mutationFn: (input: InstrumentInput) => createInstrument(input),
    onSuccess: async (_created, input) => {
      announce(`Actif « ${input.name} » ajouté.`)
      setName('')
      setIsin('')
      setTicker('')
      setErrors({})
      await queryClient.invalidateQueries({ queryKey: keys.instruments })
    },
    onError: (failure) => {
      const split = splitApiError(failure, FIELDS)
      setErrors(split.fields)
      setGeneral(split.general)
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    setGeneral(null)
    const problems: Record<string, string> = {}
    const code = isin.trim().toUpperCase()
    if (!name.trim()) problems.name = "Le nom de l'actif est obligatoire."
    if (code && !ISIN_SHAPE.test(code)) {
      problems.isin =
        'Un ISIN fait 12 caractères : 2 lettres, 9 caractères alphanumériques et un chiffre.'
    }
    if (!/^[A-Z]{3}$/.test(currency)) problems.currency = 'La devise est un code de trois lettres.'
    setErrors(problems)
    if (Object.keys(problems).length > 0) return

    const input: InstrumentInput = { kind, name: name.trim(), currency }
    if (code) input.isin = code
    if (ticker.trim()) input.price_ticker = ticker.trim()
    create.mutate(input)
  }

  const managed = instruments.data?.find((item: Instrument) => item.id === managedId)

  return (
    <section>
      <h2 className="text-xl font-semibold">Actifs</h2>
      <p className="mt-1 text-sm text-muted">
        Les actions, ETF, fonds, SCPI et fonds en euros que vous détenez dans vos comptes.
      </p>
      <div className="mt-3">
        <button
          type="button"
          className={secondaryButtonClass}
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? 'Mise à jour…' : 'Mettre à jour les cours'}
        </button>
        {refresh.isError && (
          <p role="alert" className="mt-2 text-danger">
            La mise à jour a échoué : les derniers prix connus restent utilisés.
          </p>
        )}
        {refresh.data && <RefreshSummary sources={refresh.data.sources} />}
      </div>

      {instruments.isPending && <LoadingState className="mt-4" />}
      {instruments.isError && (
        <ErrorState
          className="mt-4"
          message="Impossible de charger les actifs."
          onRetry={() => void instruments.refetch()}
        />
      )}
      {instruments.data && instruments.data.length === 0 && (
        <p className="mt-4 text-muted">
          Aucun actif pour le moment. Ajoutez votre premier actif ci-dessous.
        </p>
      )}
      {instruments.data && instruments.data.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table aria-label="Actifs" className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Nom</th>
                <th className="py-2 pr-4 font-medium">Type</th>
                <th className="py-2 pr-4 font-medium">ISIN</th>
                <th className="py-2 pr-4 font-medium">Devise</th>
                <th className="py-2 pr-4 font-medium">Prix</th>
                <th className="py-2 pr-4 font-medium">Ticker</th>
                <th className="py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {instruments.data.map((item) => (
                <tr key={item.id} className="border-t border-line">
                  <th scope="row" className="py-2 pr-4 font-medium">
                    {item.name}
                  </th>
                  <td className="py-2 pr-4">{INSTRUMENT_KIND_LABELS[item.kind]}</td>
                  <td className="py-2 pr-4">{item.isin ?? '—'}</td>
                  <td className="py-2 pr-4">{item.currency}</td>
                  <td className="py-2 pr-4">{PRICE_MODE_LABELS[item.price_mode ?? 'MANUAL']}</td>
                  <td className="py-2 pr-4">{item.price_ticker ?? '—'}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      className="text-brand underline"
                      aria-label={`Gérer ${item.name}`}
                      onClick={() => setManagedId(item.id)}
                    >
                      Gérer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {managed && (
        <InstrumentPanel key={managed.id} instrument={managed} onClose={() => setManagedId(null)} />
      )}

      <form
        onSubmit={submit}
        noValidate
        aria-label="Nouvel actif"
        className="mt-8 max-w-md rounded-2xl border border-line bg-card p-5 shadow-sm"
      >
        <h3 className="font-medium">Ajouter un actif</h3>
        <SelectField
          id="ins-kind"
          label="Type d'actif"
          value={kind}
          onChange={(value) => setKind(value as InstrumentKind)}
          options={KIND_OPTIONS}
          error={errors.kind}
        />
        <TextField id="ins-name" label="Nom" value={name} onChange={setName} error={errors.name} />
        <TextField
          id="ins-isin"
          label="Code ISIN"
          value={isin}
          onChange={setIsin}
          error={errors.isin}
          hint="Facultatif. Exemple : IE00B4L5Y983."
        />
        <TextField
          id="ins-currency"
          label="Devise"
          value={currency}
          onChange={(value) => setCurrency(value.toUpperCase())}
          error={errors.currency}
        />
        <TextField
          id="ins-ticker"
          label="Ticker de cotation"
          value={ticker}
          onChange={setTicker}
          error={errors.price_ticker}
          hint="Facultatif. Sert à récupérer les cours si vous activez la mise à jour automatique."
        />
        {general && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {general}
          </p>
        )}
        <button type="submit" className={`${buttonClass} mt-4`} disabled={create.isPending}>
          Ajouter l'actif
        </button>
      </form>
    </section>
  )
}

function describe(source: RefreshSource): string {
  const name = SOURCE_NAMES[source.source] ?? source.source
  if (source.status === 'disabled') return `${name} : récupération désactivée.`
  if (source.status === 'failed') {
    return `${name} : échec — ${source.message ?? 'source indisponible'}. Les derniers prix connus restent utilisés.`
  }
  const count = source.updated ?? 0
  const done = `${name} : ${count} ${count > 1 ? 'mises à jour' : 'mise à jour'}`
  return source.status === 'partial' ? `${done}. ${source.message ?? ''}`.trim() : done
}

function RefreshSummary({ sources }: { sources: RefreshSource[] }) {
  const disabled = sources.some((source) => source.status === 'disabled')
  return (
    <div role="status" className="mt-2 text-sm">
      <ul className="space-y-1">
        {sources.map((source) => (
          <li key={source.source}>{describe(source)}</li>
        ))}
      </ul>
      {disabled && (
        <Link className="text-brand underline" to="/reglages">
          Activer dans les réglages
        </Link>
      )}
    </div>
  )
}
