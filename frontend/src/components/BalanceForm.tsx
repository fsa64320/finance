import { type FormEvent, useState } from 'react'

import type { DeclaredBalanceInput, Instrument } from '../api/types'
import { normalizeDecimalInput } from '../lib/decimal-input'
import { splitApiError } from '../lib/form-errors'
import { SelectField, TextField, buttonClass, secondaryButtonClass } from './fields'

interface BalanceFormProps {
  accountId: string
  currency: string
  /** Actifs sans cours : fonds en euros et trésorerie. */
  instruments: Instrument[]
  onSubmit: (input: DeclaredBalanceInput) => Promise<unknown>
  onCancel: () => void
}

const FIELDS = ['instrument_id', 'balance_date', 'amount', 'currency'] as const

export default function BalanceForm({
  accountId,
  currency,
  instruments,
  onSubmit,
  onCancel,
}: BalanceFormProps) {
  const [instrumentId, setInstrumentId] = useState('')
  const [date, setDate] = useState('')
  const [amount, setAmount] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  if (instruments.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-card p-5">
        <p>
          Aucun actif sans cours. Créez d'abord un « Fonds en euros » ou une « Trésorerie » dans la
          page Actifs.
        </p>
        <button type="button" className={`${secondaryButtonClass} mt-3`} onClick={onCancel}>
          Fermer
        </button>
      </div>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setGeneral(null)
    const problems: Record<string, string> = {}
    if (!instrumentId) problems.instrument_id = "Choisissez l'actif."
    if (!date) problems.balance_date = 'La date est obligatoire.'
    const normalized = normalizeDecimalInput(amount)
    if (normalized === null) problems.amount = 'Saisissez un nombre, par exemple 5 000.'
    else if (normalized.startsWith('-')) problems.amount = 'Le solde ne peut pas être négatif.'
    setErrors(problems)
    if (Object.keys(problems).length > 0 || normalized === null) return

    setPending(true)
    try {
      await onSubmit({
        account_id: accountId,
        instrument_id: instrumentId,
        balance_date: date,
        amount: normalized,
        currency,
      })
    } catch (failure) {
      const split = splitApiError(failure, FIELDS)
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
      className="rounded-2xl border border-line bg-card p-5 shadow-sm"
      aria-label="Déclarer un solde"
    >
      <SelectField
        id="bal-instrument"
        label="Actif sans cours"
        value={instrumentId}
        onChange={setInstrumentId}
        placeholder="Choisir un actif"
        options={instruments.map((item) => ({ value: item.id, label: item.name }))}
        error={errors.instrument_id}
      />
      <TextField
        id="bal-date"
        label="Date du solde"
        type="date"
        value={date}
        onChange={setDate}
        error={errors.balance_date}
      />
      <TextField
        id="bal-amount"
        label={`Solde (${currency})`}
        inputMode="decimal"
        value={amount}
        onChange={setAmount}
        error={errors.amount}
      />
      {general && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {general}
        </p>
      )}
      <div className="mt-4 flex gap-3">
        <button type="submit" className={buttonClass} disabled={pending}>
          {pending ? 'Enregistrement…' : 'Enregistrer le solde'}
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  )
}
