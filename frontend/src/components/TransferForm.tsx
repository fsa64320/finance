import { type FormEvent, useState } from 'react'

import type { Account, TransferInput } from '../api/types'
import { isPositiveDecimal, normalizeDecimalInput } from '../lib/decimal-input'
import { splitApiError } from '../lib/form-errors'
import { SelectField, TextField, buttonClass, secondaryButtonClass } from './fields'

interface TransferFormProps {
  /** Comptes ouverts entre lesquels on peut virer. */
  accounts: Pick<Account, 'id' | 'name' | 'currency'>[]
  fromAccountId: string
  onSubmit: (input: TransferInput) => Promise<unknown>
  onCancel: () => void
}

const FIELDS = [
  'from_account_id',
  'to_account_id',
  'trade_date',
  'amount',
  'currency',
  'label',
] as const

export default function TransferForm({
  accounts,
  fromAccountId,
  onSubmit,
  onCancel,
}: TransferFormProps) {
  const [from, setFrom] = useState(fromAccountId)
  const [to, setTo] = useState('')
  const [tradeDate, setTradeDate] = useState('')
  const [amount, setAmount] = useState('')
  const [label, setLabel] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  if (accounts.length < 2) {
    return (
      <div className="rounded-2xl border border-line bg-card p-5">
        <p>Un virement relie deux comptes : il faut au moins deux comptes ouverts.</p>
        <button type="button" className={`${secondaryButtonClass} mt-3`} onClick={onCancel}>
          Fermer
        </button>
      </div>
    )
  }

  const source = accounts.find((account) => account.id === from)
  const currency = source?.currency ?? 'EUR'
  const options = accounts.map((account) => ({ value: account.id, label: account.name }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setGeneral(null)
    const problems: Record<string, string> = {}
    if (!to) problems.to_account_id = 'Choisissez le compte destination.'
    else if (to === from) problems.to_account_id = 'Choisissez deux comptes différents.'
    if (!tradeDate) problems.trade_date = 'La date est obligatoire.'
    const normalized = normalizeDecimalInput(amount)
    if (normalized === null) {
      problems.amount =
        amount.trim() === ''
          ? 'Le montant doit être strictement positif.'
          : 'Saisissez un nombre, par exemple 1 250,50.'
    } else if (!isPositiveDecimal(normalized)) {
      problems.amount = 'Le montant doit être strictement positif.'
    }
    setErrors(problems)
    if (Object.keys(problems).length > 0 || normalized === null) return

    const input: TransferInput = {
      from_account_id: from,
      to_account_id: to,
      trade_date: tradeDate,
      amount: normalized,
      currency,
    }
    if (label.trim()) input.label = label.trim()
    setPending(true)
    try {
      await onSubmit(input)
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
      aria-label="Nouveau virement"
    >
      <SelectField
        id="tr-from"
        label="Compte source"
        value={from}
        onChange={setFrom}
        options={options}
        error={errors.from_account_id}
      />
      <SelectField
        id="tr-to"
        label="Compte destination"
        value={to}
        onChange={setTo}
        placeholder="Choisir un compte"
        options={options}
        error={errors.to_account_id}
      />
      <TextField
        id="tr-date"
        label="Date"
        type="date"
        value={tradeDate}
        onChange={setTradeDate}
        error={errors.trade_date}
      />
      <TextField
        id="tr-amount"
        label={`Montant (${currency})`}
        inputMode="decimal"
        value={amount}
        onChange={setAmount}
        error={errors.amount}
      />
      <TextField
        id="tr-label"
        label="Libellé"
        value={label}
        onChange={setLabel}
        error={errors.label}
      />
      {general && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {general}
        </p>
      )}
      <div className="mt-4 flex gap-3">
        <button type="submit" className={buttonClass} disabled={pending}>
          {pending ? 'Enregistrement…' : 'Enregistrer le virement'}
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  )
}
