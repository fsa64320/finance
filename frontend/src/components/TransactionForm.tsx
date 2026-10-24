import Decimal from 'decimal.js-light'
import { type FormEvent, useState } from 'react'

import type { Account, Instrument, Transaction, TransactionInput } from '../api/types'
import { isPositiveDecimal, normalizeDecimalInput } from '../lib/decimal-input'
import { splitApiError } from '../lib/form-errors'
import { formatDate, formatQuantity } from '../lib/format'
import {
  INSTRUMENT_TYPES,
  TRADE_TYPES,
  TRANSACTION_TYPE_LABELS,
  type TransactionType,
  transactionTypesFor,
} from '../lib/labels'
import { SelectField, TextField, buttonClass, secondaryButtonClass } from './fields'

interface TransactionFormProps {
  account: Pick<Account, 'id' | 'type' | 'currency' | 'opened_on'>
  instruments: Instrument[]
  /** Quantité détenue par actif, pour prévenir d'une vente excédentaire. */
  holdings?: Record<string, string>
  /** Opération à modifier ; absente pour une saisie. */
  initial?: Transaction
  onSubmit: (input: TransactionInput) => Promise<{ warnings: string[] } | void>
  onCancel: () => void
}

const FIELDS = [
  'type',
  'trade_date',
  'instrument_id',
  'quantity',
  'unit_price',
  'amount',
  'fees',
  'unlock_date',
  'label',
] as const

const POSITIVE_AMOUNT = 'Le montant doit être strictement positif.'
const NOT_A_NUMBER = 'Saisissez un nombre, par exemple 1 250,50.'

function initialAmount(initial?: Transaction): string {
  return initial ? initial.cash_amount.replace(/^-/, '') : ''
}

export default function TransactionForm({
  account,
  instruments,
  holdings = {},
  initial,
  onSubmit,
  onCancel,
}: TransactionFormProps) {
  const allowed = transactionTypesFor(account.type)
  const [type, setType] = useState<TransactionType>(
    initial && allowed.includes(initial.type) ? initial.type : 'DEPOSIT',
  )
  const [tradeDate, setTradeDate] = useState(initial?.trade_date ?? '')
  const [instrumentId, setInstrumentId] = useState(initial?.instrument_id ?? '')
  const [quantity, setQuantity] = useState(initial?.quantity ?? '')
  const [unitPrice, setUnitPrice] = useState(initial?.unit_price ?? '')
  const [amount, setAmount] = useState(initialAmount(initial))
  const [fees, setFees] = useState(initial?.fees && initial.fees !== '0' ? initial.fees : '')
  const [unlockDate, setUnlockDate] = useState(initial?.unlock_date ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [pending, setPending] = useState(false)

  const currency = account.currency
  const isTrade = TRADE_TYPES.includes(type)
  const needsInstrument = INSTRUMENT_TYPES.includes(type)
  const showUnlock = account.type === 'PEE' && (type === 'DEPOSIT' || type === 'EMPLOYER_MATCH')

  function oversellWarning(): string | null {
    if (type !== 'SELL' || !instrumentId) return null
    const held = holdings[instrumentId]
    const sold = normalizeDecimalInput(quantity)
    if (held === undefined || sold === null || !isPositiveDecimal(sold)) return null
    if (!new Decimal(sold).gt(held)) return null
    return `La vente dépasse la quantité détenue (${formatQuantity(held)}) : l'historique est peut-être incomplet.`
  }

  function validate(): { problems: Record<string, string>; input: TransactionInput | null } {
    const problems: Record<string, string> = {}
    if (!tradeDate) problems.trade_date = 'La date est obligatoire.'
    else if (tradeDate < account.opened_on) {
      problems.trade_date = `La date précède l'ouverture du compte (${formatDate(account.opened_on)}).`
    }
    const input: Record<string, string> = {
      account_id: account.id,
      type,
      trade_date: tradeDate,
      currency,
    }
    if (needsInstrument) {
      if (!instrumentId) problems.instrument_id = "Choisissez l'actif."
      else input.instrument_id = instrumentId
    }
    if (isTrade) {
      const q = normalizeDecimalInput(quantity)
      if (q === null || !isPositiveDecimal(q))
        problems.quantity = 'La quantité doit être strictement positive.'
      else input.quantity = q
      const p = normalizeDecimalInput(unitPrice)
      if (p === null || !isPositiveDecimal(p))
        problems.unit_price = 'Le prix doit être strictement positif.'
      else input.unit_price = p
      if (fees.trim() !== '') {
        const f = normalizeDecimalInput(fees)
        if (f === null) problems.fees = NOT_A_NUMBER
        else if (new Decimal(f).lt(0)) problems.fees = 'Les frais ne peuvent pas être négatifs.'
        else input.fees = f
      }
    } else {
      const a = normalizeDecimalInput(amount)
      if (a === null) problems.amount = amount.trim() === '' ? POSITIVE_AMOUNT : NOT_A_NUMBER
      else if (!isPositiveDecimal(a)) problems.amount = POSITIVE_AMOUNT
      else input.amount = a
    }
    if (showUnlock && unlockDate) input.unlock_date = unlockDate
    if (label.trim()) input.label = label.trim()
    return {
      problems,
      input: Object.keys(problems).length === 0 ? (input as unknown as TransactionInput) : null,
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setGeneral(null)
    setWarnings([])
    const { problems, input } = validate()
    setErrors(problems)
    if (input === null) return
    setPending(true)
    try {
      const result = await onSubmit(input)
      setWarnings(result?.warnings ?? [])
    } catch (failure) {
      const split = splitApiError(failure, FIELDS, { instrument: 'instrument_id' })
      setErrors(split.fields)
      setGeneral(split.general)
    } finally {
      setPending(false)
    }
  }

  const oversell = oversellWarning()

  return (
    <form
      onSubmit={submit}
      noValidate
      className="rounded-2xl border border-line bg-card p-5 shadow-sm"
      aria-label={initial ? 'Modifier une opération' : 'Nouvelle opération'}
    >
      <SelectField
        id="tx-type"
        label="Type d'opération"
        value={type}
        onChange={(value) => setType(value as TransactionType)}
        options={allowed.map((kind) => ({ value: kind, label: TRANSACTION_TYPE_LABELS[kind] }))}
        error={errors.type}
      />
      <TextField
        id="tx-date"
        label="Date"
        type="date"
        value={tradeDate}
        onChange={setTradeDate}
        error={errors.trade_date}
      />
      {needsInstrument && (
        <SelectField
          id="tx-instrument"
          label="Actif"
          value={instrumentId}
          onChange={setInstrumentId}
          placeholder="Choisir un actif"
          options={instruments.map((item) => ({ value: item.id, label: item.name }))}
          error={errors.instrument_id}
        />
      )}
      {isTrade ? (
        <>
          <TextField
            id="tx-quantity"
            label="Quantité"
            inputMode="decimal"
            value={quantity}
            onChange={setQuantity}
            error={errors.quantity}
          />
          <TextField
            id="tx-price"
            label={`Prix unitaire (${currency})`}
            inputMode="decimal"
            value={unitPrice}
            onChange={setUnitPrice}
            error={errors.unit_price}
          />
          <TextField
            id="tx-fees"
            label={`Frais (${currency})`}
            inputMode="decimal"
            value={fees}
            onChange={setFees}
            error={errors.fees}
          />
        </>
      ) : (
        <TextField
          id="tx-amount"
          label={`Montant (${currency})`}
          inputMode="decimal"
          value={amount}
          onChange={setAmount}
          error={errors.amount}
        />
      )}
      {showUnlock && (
        <TextField
          id="tx-unlock"
          label="Date de déblocage"
          type="date"
          value={unlockDate}
          onChange={setUnlockDate}
          error={errors.unlock_date}
        />
      )}
      <TextField
        id="tx-label"
        label="Libellé"
        value={label}
        onChange={setLabel}
        error={errors.label}
      />

      {oversell && (
        <p role="status" className="mt-3 rounded-lg bg-warn-bg p-3 text-sm text-warn-ink">
          {oversell}
        </p>
      )}
      {warnings.length > 0 && (
        <div role="status" className="mt-3 rounded-lg bg-warn-bg p-3 text-sm text-warn-ink">
          {warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}
      {general && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {general}
        </p>
      )}

      <div className="mt-4 flex gap-3">
        <button type="submit" className={buttonClass} disabled={pending}>
          {pending ? 'Enregistrement…' : initial ? 'Enregistrer la modification' : 'Enregistrer'}
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  )
}
