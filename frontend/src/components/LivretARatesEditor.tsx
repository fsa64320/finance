import { type FormEvent, useState } from 'react'

import type { LivretARate } from '../api/types'
import { isPositiveDecimal, normalizeDecimalInput } from '../lib/decimal-input'
import { splitApiError } from '../lib/form-errors'
import { formatDate, formatPercent } from '../lib/format'
import { TextField, buttonClass } from './fields'

interface LivretARatesEditorProps {
  rates: LivretARate[]
  onAdd: (rate: LivretARate) => Promise<unknown>
}

const FIELDS = ['effective_from', 'value'] as const

/** Table des taux datés du Livret A : le taux en vigueur est le dernier dont la date est passée. */
export default function LivretARatesEditor({ rates, onAdd }: LivretARatesEditorProps) {
  const [date, setDate] = useState('')
  const [rate, setRate] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setGeneral(null)
    const problems: Record<string, string> = {}
    if (!date) problems.effective_from = "La date d'effet est obligatoire."
    const normalized = normalizeDecimalInput(rate)
    if (rate.trim() === '') problems.value = 'Saisissez le taux annuel.'
    else if (normalized === null || (isPositiveDecimal(normalized) && Number(normalized) > 100)) {
      problems.value = 'Le taux est un pourcentage entre 0 et 100.'
    }
    setErrors(problems)
    if (Object.keys(problems).length > 0 || normalized === null) return

    setPending(true)
    try {
      await onAdd({ effective_from: date, value: normalized })
      setDate('')
      setRate('')
    } catch (failure) {
      const split = splitApiError(failure, FIELDS)
      setErrors(split.fields)
      setGeneral(split.general)
    } finally {
      setPending(false)
    }
  }

  return (
    <div>
      <p className="text-sm text-muted">
        Ces taux servent à estimer les intérêts du Livret A, par quinzaine. Ils sont indicatifs :
        vérifiez-les auprès de votre banque et ajoutez le nouveau taux à chaque changement.
      </p>
      {rates.length === 0 ? (
        <p className="mt-3 text-muted">Aucun taux enregistré : les intérêts ne sont pas estimés.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table aria-label="Taux du Livret A" className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th scope="col" className="py-2 pr-4 font-medium">
                  En vigueur depuis le
                </th>
                <th scope="col" className="py-2 font-medium">
                  Taux annuel
                </th>
              </tr>
            </thead>
            <tbody>
              {rates.map((item) => (
                <tr key={item.effective_from} className="border-t border-line">
                  <td className="py-2 pr-4">{formatDate(item.effective_from)}</td>
                  <td className="py-2">{formatPercent(item.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={submit} noValidate aria-label="Ajouter un taux" className="mt-4 max-w-sm">
        <TextField
          id="rate-date"
          label="Date d'effet"
          type="date"
          value={date}
          onChange={setDate}
          error={errors.effective_from}
        />
        <TextField
          id="rate-value"
          label="Taux annuel (%)"
          inputMode="decimal"
          value={rate}
          onChange={setRate}
          error={errors.value}
          hint="Exemple : 1,7"
        />
        {general && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {general}
          </p>
        )}
        <button type="submit" className={`${buttonClass} mt-4`} disabled={pending}>
          Ajouter le taux
        </button>
      </form>
    </div>
  )
}
