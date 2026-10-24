import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { createAccount, listAccounts } from '../api/accounts'
import { keys } from '../api/keys'
import type { AccountInput, AccountType } from '../api/types'
import { SelectField, TextField, buttonClass } from '../components/fields'
import { splitApiError } from '../lib/form-errors'
import { formatDate, formatMoney } from '../lib/format'
import { ACCOUNT_TYPE_LABELS } from '../lib/labels'

const FIELDS = ['type', 'name', 'institution', 'opened_on', 'currency'] as const
const TYPE_OPTIONS = (Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[]).map((type) => ({
  value: type,
  label: ACCOUNT_TYPE_LABELS[type],
}))

export default function Accounts() {
  const queryClient = useQueryClient()
  const [includeClosed, setIncludeClosed] = useState(false)
  const accounts = useQuery({
    queryKey: keys.accountList(includeClosed),
    queryFn: () => listAccounts({ includeClosed }),
  })

  const [type, setType] = useState<AccountType>('PEA')
  const [name, setName] = useState('')
  const [institution, setInstitution] = useState('')
  const [openedOn, setOpenedOn] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: (input: AccountInput) => createAccount(input),
    onSuccess: async () => {
      setName('')
      setInstitution('')
      setOpenedOn('')
      setErrors({})
      await queryClient.invalidateQueries({ queryKey: keys.accounts })
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
    if (!name.trim()) problems.name = 'Le nom du compte est obligatoire.'
    if (!openedOn) problems.opened_on = "La date d'ouverture est obligatoire."
    setErrors(problems)
    if (Object.keys(problems).length > 0) return
    const input: AccountInput = { type, name: name.trim(), opened_on: openedOn }
    if (institution.trim()) input.institution = institution.trim()
    create.mutate(input)
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">Comptes</h2>

      <label className="mt-3 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeClosed}
          onChange={(event) => setIncludeClosed(event.target.checked)}
        />
        Afficher les comptes clos
      </label>

      {accounts.isPending && <p className="mt-4 text-muted">Chargement…</p>}
      {accounts.isError && (
        <p role="alert" className="mt-4 text-danger">
          Impossible de charger les comptes.
        </p>
      )}
      {accounts.data && accounts.data.length === 0 && (
        <p className="mt-4 text-muted">
          Aucun compte pour le moment. Créez votre premier compte ci-dessous.
        </p>
      )}
      {accounts.data && accounts.data.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table aria-label="Comptes" className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Compte</th>
                <th className="py-2 pr-4 font-medium">Type</th>
                <th className="py-2 pr-4 font-medium">Établissement</th>
                <th className="py-2 pr-4 font-medium">Valeur</th>
                <th className="py-2 font-medium">Statut</th>
              </tr>
            </thead>
            <tbody>
              {accounts.data.map((item) => (
                <tr key={item.id} className="border-t border-line">
                  <td className="py-2 pr-4 font-medium">
                    <Link className="text-brand underline" to={`/comptes/${item.id}`}>
                      {item.name}
                    </Link>
                  </td>
                  <td className="py-2 pr-4">{ACCOUNT_TYPE_LABELS[item.type]}</td>
                  <td className="py-2 pr-4">{item.institution ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <span>{formatMoney(item.value, item.currency)}</span>{' '}
                    {item.estimated && (
                      <span className="rounded bg-warn-bg px-1.5 py-0.5 text-xs text-warn-ink">
                        Estimé
                      </span>
                    )}
                  </td>
                  <td className="py-2">
                    {item.closed_on ? `Clos le ${formatDate(item.closed_on)}` : 'Ouvert'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form
        onSubmit={submit}
        noValidate
        aria-label="Nouveau compte"
        className="mt-8 max-w-md rounded-2xl border border-line bg-card p-5 shadow-sm"
      >
        <h3 className="font-medium">Créer un compte</h3>
        <SelectField
          id="acc-type"
          label="Type de compte"
          value={type}
          onChange={(value) => setType(value as AccountType)}
          options={TYPE_OPTIONS}
          error={errors.type}
        />
        <TextField
          id="acc-name"
          label="Nom du compte"
          value={name}
          onChange={setName}
          error={errors.name}
        />
        <TextField
          id="acc-institution"
          label="Établissement"
          value={institution}
          onChange={setInstitution}
          error={errors.institution}
        />
        <TextField
          id="acc-opened"
          label="Date d'ouverture"
          type="date"
          value={openedOn}
          onChange={setOpenedOn}
          error={errors.opened_on}
        />
        {general && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {general}
          </p>
        )}
        <button type="submit" className={`${buttonClass} mt-4`} disabled={create.isPending}>
          Créer le compte
        </button>
      </form>
    </section>
  )
}
