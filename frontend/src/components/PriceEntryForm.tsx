import { type FormEvent, useState } from 'react'

import type { Instrument, PriceInput, PriceKind } from '../api/types'
import { isPositiveDecimal, normalizeDecimalInput } from '../lib/decimal-input'
import { splitApiError } from '../lib/form-errors'
import { TextField, buttonClass, secondaryButtonClass } from './fields'

interface PriceEntryFormProps {
  instrument: Pick<Instrument, 'id' | 'kind' | 'currency'>
  /** Reçoit un prix par champ rempli (deux pour une SCPI). */
  onSubmit: (inputs: PriceInput[]) => Promise<unknown>
  onCancel?: () => void
}

interface PriceField {
  kind: PriceKind
  key: string
  label: string
}

const FIELDS = ['price_date', 'kind', 'value', 'currency'] as const

function fieldsFor(kind: Instrument['kind']): PriceField[] {
  if (kind === 'SCPI') {
    return [
      { kind: 'SUBSCRIPTION', key: 'subscription', label: 'Prix de souscription' },
      { kind: 'REDEMPTION', key: 'redemption', label: 'Prix de retrait' },
    ]
  }
  if (kind === 'FUND' || kind === 'FCPE') {
    return [{ kind: 'NAV', key: 'nav', label: 'Valeur liquidative' }]
  }
  return [{ kind: 'MARKET', key: 'market', label: 'Cours' }]
}

const today = () => new Date().toISOString().slice(0, 10)

/** Saisie manuelle d'un cours, d'une valeur liquidative ou des prix d'une SCPI à une date. */
export default function PriceEntryForm({ instrument, onSubmit, onCancel }: PriceEntryFormProps) {
  const fields = fieldsFor(instrument.kind)
  const [date, setDate] = useState('')
  const [values, setValues] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const isScpi = instrument.kind === 'SCPI'

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setGeneral(null)
    const problems: Record<string, string> = {}
    if (!date) problems.price_date = 'La date est obligatoire.'
    else if (date > today()) problems.price_date = 'La date ne peut pas être dans le futur.'

    const inputs: PriceInput[] = []
    for (const field of fields) {
      const raw = (values[field.key] ?? '').trim()
      if (raw === '') continue
      const normalized = normalizeDecimalInput(raw)
      if (normalized === null) {
        problems[field.key] = 'Saisissez un nombre, par exemple 90,25.'
      } else if (!isPositiveDecimal(normalized)) {
        problems[field.key] = 'Le prix doit être strictement positif.'
      } else {
        inputs.push({
          instrument_id: instrument.id,
          price_date: date,
          kind: field.kind,
          value: normalized,
          currency: instrument.currency,
        })
      }
    }
    if (
      inputs.length === 0 &&
      Object.keys(problems).filter((key) => key !== 'price_date').length === 0
    ) {
      const first = fields[0]!
      if (isScpi) problems[first.key] = 'Saisissez au moins un des deux prix.'
      else problems[first.key] = 'Saisissez un prix.'
    }
    setErrors(problems)
    if (Object.keys(problems).length > 0) return

    setPending(true)
    try {
      await onSubmit(inputs)
      setValues({})
      setDate('')
    } catch (failure) {
      const split = splitApiError(failure, [...FIELDS, ...fields.map((field) => field.key)], {
        value: fields[0]!.key,
        kind: fields[0]!.key,
      })
      setErrors(split.fields)
      setGeneral(split.general)
    } finally {
      setPending(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Saisir un prix"
      className="rounded-2xl border border-line bg-card p-5 shadow-sm"
    >
      <TextField
        id={`price-date-${instrument.id}`}
        label="Date du prix"
        type="date"
        value={date}
        onChange={setDate}
        error={errors.price_date}
      />
      {fields.map((field) => (
        <TextField
          key={field.key}
          id={`price-${field.key}-${instrument.id}`}
          label={`${field.label} (${instrument.currency})`}
          inputMode="decimal"
          value={values[field.key] ?? ''}
          onChange={(value) => setValues({ ...values, [field.key]: value })}
          error={errors[field.key]}
        />
      ))}
      {isScpi && (
        <p className="mt-2 text-sm text-muted">
          Le prix de revient suit le prix de souscription, la valeur le prix de retrait : l’écart
          initial entre les deux reste visible.
        </p>
      )}
      {general && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {general}
        </p>
      )}
      <div className="mt-4 flex gap-3">
        <button type="submit" className={buttonClass} disabled={pending}>
          {pending ? 'Enregistrement…' : 'Enregistrer'}
        </button>
        {onCancel && (
          <button type="button" className={secondaryButtonClass} onClick={onCancel}>
            Annuler
          </button>
        )}
      </div>
    </form>
  )
}
