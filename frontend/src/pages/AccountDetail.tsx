import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { declareBalance, getAccount, listAccounts, patchAccount } from '../api/accounts'
import { ApiError } from '../api/client'
import { listInstruments } from '../api/instruments'
import { keys } from '../api/keys'
import {
  createTransaction,
  createTransfer,
  getTransaction,
  listTransactions,
  updateTransaction,
  voidTransaction,
} from '../api/transactions'
import type {
  AccountDetail as AccountDetailData,
  Instrument,
  Transaction,
  TransactionInput,
} from '../api/types'
import BalanceForm from '../components/BalanceForm'
import ModificationHistory from '../components/ModificationHistory'
import TransactionForm from '../components/TransactionForm'
import TransferForm from '../components/TransferForm'
import {
  TextField,
  buttonClass,
  secondaryButtonClass,
  smallButtonClass,
} from '../components/fields'
import {
  formatDate,
  formatMoney,
  formatPercentOf,
  formatQuantity,
  formatUnitPrice,
} from '../lib/format'
import { ACCOUNT_TYPE_LABELS, TRANSACTION_TYPE_LABELS } from '../lib/labels'

type Panel =
  | { kind: 'new' }
  | { kind: 'edit'; transaction: Transaction }
  | { kind: 'transfer' }
  | { kind: 'balance' }
  | { kind: 'rename' }
  | null

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function CapGauge({ detail }: { detail: AccountDetailData }) {
  const usage = detail.deposit_cap_usage
  if (!usage?.deposited || !usage.cap) return null
  const isLivret = detail.type === 'LIVRET_A'
  const label = isLivret ? 'Plafond du Livret A utilisé' : 'Plafond du PEA utilisé'
  const percent = formatPercentOf(usage.deposited, usage.cap, { capAt100: true })
  const money = (value: string) => formatMoney(value, detail.currency)
  const text = isLivret
    ? `${money(usage.deposited)} de solde sur un plafond de ${money(usage.cap)}`
    : `${money(usage.deposited)} versés sur un plafond de ${money(usage.cap)}`
  return (
    <div className="mt-4">
      <p data-testid="cap-text" className="text-sm">
        {text}
      </p>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Number(percent)}
        className="mt-1 h-2 w-full overflow-hidden rounded bg-line"
      >
        <div
          className={`h-full ${usage.exceeded ? 'bg-danger' : 'bg-brand'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {usage.exceeded && <p className="mt-1 text-sm font-medium text-danger">Plafond dépassé</p>}
    </div>
  )
}

function PositionsTable({
  detail,
  instruments,
}: {
  detail: AccountDetailData
  instruments: Map<string, Instrument>
}) {
  if (detail.positions.length === 0) {
    return <p className="mt-2 text-muted">Aucune position pour le moment.</p>
  }
  return (
    <div className="mt-2 overflow-x-auto">
      <table aria-label="Positions" className="w-full text-left text-sm">
        <thead className="text-muted">
          <tr>
            <th className="py-2 pr-4 font-medium">Actif</th>
            <th className="py-2 pr-4 font-medium">Quantité</th>
            <th className="py-2 pr-4 font-medium">Prix de revient unitaire</th>
            <th className="py-2 font-medium">Valeur</th>
          </tr>
        </thead>
        <tbody>
          {detail.positions.map((position) => (
            <tr key={position.instrument_id} className="border-t border-line">
              <td className="py-2 pr-4 font-medium">
                {instruments.get(position.instrument_id)?.name ?? position.instrument_id}
              </td>
              <td className="py-2 pr-4">{formatQuantity(position.quantity)}</td>
              <td className="py-2 pr-4">
                {position.unit_cost ? formatUnitPrice(position.unit_cost, detail.currency) : '—'}
              </td>
              <td className="py-2">
                {position.value === null ? (
                  <span>Non valorisée</span>
                ) : (
                  <span>{formatMoney(position.value, detail.currency)}</span>
                )}{' '}
                {position.estimated && (
                  <span className="rounded bg-warn-bg px-1.5 py-0.5 text-xs text-warn-ink">
                    estimé
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RenameForm({
  detail,
  onSubmit,
  onCancel,
}: {
  detail: AccountDetailData
  onSubmit: (patch: { name: string; institution: string }) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(detail.name)
  const [institution, setInstitution] = useState(detail.institution ?? '')
  const [error, setError] = useState<string | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) {
      setError('Le nom du compte est obligatoire.')
      return
    }
    onSubmit({ name: name.trim(), institution: institution.trim() })
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Renommer le compte"
      className="mt-4 max-w-md rounded-2xl border border-line bg-card p-5 shadow-sm"
    >
      <TextField
        id="rn-name"
        label="Nom du compte"
        value={name}
        onChange={setName}
        error={error ?? undefined}
      />
      <TextField
        id="rn-institution"
        label="Établissement"
        value={institution}
        onChange={setInstitution}
      />
      <div className="mt-4 flex gap-3">
        <button type="submit" className={buttonClass}>
          Enregistrer le nom
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  )
}

function TransactionRow({
  transaction,
  instruments,
  currency,
  onEdit,
  onVoid,
}: {
  transaction: Transaction
  instruments: Map<string, Instrument>
  currency: string
  onEdit: (transaction: Transaction) => void
  onVoid: (transaction: Transaction) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const history = useQuery({
    queryKey: keys.transactionHistory(transaction.id),
    queryFn: () => getTransaction(transaction.id),
    enabled: showHistory,
  })
  const isTransfer = transaction.transfer_group_id != null
  const instrumentName = transaction.instrument_id
    ? (instruments.get(transaction.instrument_id)?.name ?? null)
    : null

  return (
    <>
      <tr className="border-t border-line align-top">
        <td className="py-2 pr-4">{formatDate(transaction.trade_date)}</td>
        <td className="py-2 pr-4">
          <div>{TRANSACTION_TYPE_LABELS[transaction.type]}</div>
          {instrumentName && <div className="text-muted">{instrumentName}</div>}
          {transaction.label && <div className="text-muted">{transaction.label}</div>}
        </td>
        <td className="py-2 pr-4 whitespace-nowrap">
          {formatMoney(transaction.cash_amount, currency)}
        </td>
        <td className="py-2">
          <div className="flex flex-wrap gap-2">
            {!isTransfer && (
              <button
                type="button"
                className={smallButtonClass}
                onClick={() => onEdit(transaction)}
              >
                Modifier
              </button>
            )}
            <button
              type="button"
              className={smallButtonClass}
              onClick={() => setShowHistory((open) => !open)}
            >
              Historique
            </button>
            {!confirming && (
              <button
                type="button"
                className={smallButtonClass}
                onClick={() => setConfirming(true)}
              >
                Annuler l’opération
              </button>
            )}
          </div>
          {confirming && (
            <div className="mt-2 text-sm">
              {isTransfer && <p>Le virement sera annulé dans les deux comptes.</p>}
              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  className={smallButtonClass}
                  onClick={() => onVoid(transaction)}
                >
                  Confirmer l’annulation
                </button>
                <button
                  type="button"
                  className={smallButtonClass}
                  onClick={() => setConfirming(false)}
                >
                  Garder
                </button>
              </div>
            </div>
          )}
        </td>
      </tr>
      {showHistory && (
        <tr>
          <td colSpan={4} className="pb-3">
            {history.isPending && <p className="text-muted">Chargement de l'historique…</p>}
            {history.isError && <p role="alert">Impossible de charger l'historique.</p>}
            {history.data && <ModificationHistory versions={history.data.versions} />}
          </td>
        </tr>
      )}
    </>
  )
}

export default function AccountDetail() {
  const { accountId = '' } = useParams()
  const queryClient = useQueryClient()
  const [panel, setPanel] = useState<Panel>(null)
  const [confirmClose, setConfirmClose] = useState(false)

  const detail = useQuery({
    queryKey: keys.accountDetail(accountId),
    queryFn: () => getAccount(accountId),
  })
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: listInstruments })
  const transactions = useInfiniteQuery({
    queryKey: keys.accountTransactions(accountId),
    queryFn: ({ pageParam }) => listTransactions({ accountId, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
  const openAccounts = useQuery({
    queryKey: keys.accountList(false),
    queryFn: () => listAccounts({ includeClosed: false }),
    enabled: panel?.kind === 'transfer',
  })

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.accounts }),
      queryClient.invalidateQueries({ queryKey: keys.transactions }),
    ])

  const patch = useMutation({
    mutationFn: (changes: Parameters<typeof patchAccount>[1]) => patchAccount(accountId, changes),
    onSuccess: async () => {
      setPanel(null)
      setConfirmClose(false)
      await refresh()
    },
  })
  const cancel = useMutation({
    mutationFn: (transaction: Transaction) => voidTransaction(transaction.id),
    onSuccess: refresh,
  })

  if (detail.isPending) return <p className="text-muted">Chargement…</p>
  if (detail.isError) {
    const missing = detail.error instanceof ApiError && detail.error.status === 404
    return (
      <div>
        <p role="alert" className="text-danger">
          {missing ? 'Compte introuvable.' : 'Impossible de charger le compte.'}
        </p>
        <Link className="mt-2 inline-block text-brand underline" to="/comptes">
          Retour aux comptes
        </Link>
      </div>
    )
  }

  const account = detail.data
  const byId = new Map((instruments.data ?? []).map((item) => [item.id, item]))
  const holdings = Object.fromEntries(account.positions.map((p) => [p.instrument_id, p.quantity]))
  const items = transactions.data?.pages.flatMap((page) => page.items) ?? []
  const canDeclareBalance = account.type === 'ASSURANCE_VIE' || account.type === 'LIVRET_A'
  const unpriced = (instruments.data ?? []).filter(
    (item) => item.kind === 'EURO_FUND' || item.kind === 'CASH',
  )

  async function saveTransaction(input: TransactionInput) {
    const result =
      panel?.kind === 'edit'
        ? await updateTransaction(panel.transaction.id, input)
        : await createTransaction(input)
    await refresh()
    if (result.warnings.length === 0) setPanel(null)
    return result
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">{account.name}</h2>
      <p className="text-sm text-muted">
        <span>{ACCOUNT_TYPE_LABELS[account.type]}</span>
        {account.institution && <span> · {account.institution}</span>}
        {account.closed_on && <span> · Clos le {formatDate(account.closed_on)}</span>}
      </p>

      <dl className="mt-4 grid max-w-md grid-cols-2 gap-y-1 text-sm">
        <dt className="text-muted">Valeur</dt>
        <dd data-testid="account-value" className="text-right text-lg font-semibold">
          {formatMoney(account.value, account.currency)}
        </dd>
        <dt className="text-muted">Liquidités</dt>
        <dd data-testid="account-cash" className="text-right">
          {formatMoney(account.cash, account.currency)}
        </dd>
        {account.locked_amount !== undefined && (
          <>
            <dt className="text-muted">Sommes bloquées</dt>
            <dd data-testid="locked-amount" className="text-right">
              {formatMoney(account.locked_amount, account.currency)}
            </dd>
          </>
        )}
      </dl>
      {account.estimated && (
        <p className="mt-1 inline-block rounded bg-warn-bg px-2 py-0.5 text-xs text-warn-ink">
          Valeur estimée
        </p>
      )}
      <CapGauge detail={account} />

      {(account.warnings ?? []).length > 0 && (
        <ul className="mt-4 list-disc pl-5 text-sm text-warn-ink">
          {(account.warnings ?? []).map((warning) => (
            <li key={`${warning.code}-${warning.instrument_id ?? ''}`}>{warning.message}</li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className={buttonClass} onClick={() => setPanel({ kind: 'new' })}>
          Nouvelle opération
        </button>
        <button
          type="button"
          className={secondaryButtonClass}
          onClick={() => setPanel({ kind: 'transfer' })}
        >
          Virement
        </button>
        {canDeclareBalance && (
          <button
            type="button"
            className={secondaryButtonClass}
            onClick={() => setPanel({ kind: 'balance' })}
          >
            Déclarer un solde
          </button>
        )}
        <button
          type="button"
          className={secondaryButtonClass}
          onClick={() => setPanel({ kind: 'rename' })}
        >
          Renommer
        </button>
        {account.closed_on ? (
          <button
            type="button"
            className={secondaryButtonClass}
            onClick={() => patch.mutate({ closed_on: null })}
          >
            Rouvrir le compte
          </button>
        ) : confirmClose ? (
          <>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => patch.mutate({ closed_on: today() })}
            >
              Confirmer la clôture
            </button>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => setConfirmClose(false)}
            >
              Garder le compte ouvert
            </button>
          </>
        ) : (
          <button
            type="button"
            className={secondaryButtonClass}
            onClick={() => setConfirmClose(true)}
          >
            Clôturer le compte
          </button>
        )}
      </div>
      {patch.isError && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {patch.error instanceof ApiError ? patch.error.message : 'La modification a échoué.'}
        </p>
      )}

      <div className="mt-4 max-w-md">
        {(panel?.kind === 'new' || panel?.kind === 'edit') && (
          <TransactionForm
            key={panel.kind === 'edit' ? panel.transaction.id : 'new'}
            account={account}
            instruments={instruments.data ?? []}
            holdings={holdings}
            initial={panel.kind === 'edit' ? panel.transaction : undefined}
            onSubmit={saveTransaction}
            onCancel={() => setPanel(null)}
          />
        )}
        {panel?.kind === 'transfer' && (
          <TransferForm
            accounts={openAccounts.data ?? []}
            fromAccountId={account.id}
            onSubmit={async (input) => {
              await createTransfer(input)
              await refresh()
              setPanel(null)
            }}
            onCancel={() => setPanel(null)}
          />
        )}
        {panel?.kind === 'balance' && (
          <BalanceForm
            accountId={account.id}
            currency={account.currency}
            instruments={unpriced}
            onSubmit={async (input) => {
              await declareBalance(input)
              await refresh()
              setPanel(null)
            }}
            onCancel={() => setPanel(null)}
          />
        )}
        {panel?.kind === 'rename' && (
          <RenameForm
            detail={account}
            onSubmit={(changes) => patch.mutate(changes)}
            onCancel={() => setPanel(null)}
          />
        )}
      </div>

      <h3 className="mt-8 text-lg font-medium">Positions</h3>
      <PositionsTable detail={account} instruments={byId} />

      <h3 className="mt-8 text-lg font-medium">Opérations</h3>
      {transactions.isPending && <p className="mt-2 text-muted">Chargement…</p>}
      {transactions.isError && (
        <p role="alert" className="mt-2 text-danger">
          Impossible de charger les opérations.
        </p>
      )}
      {transactions.data && items.length === 0 && (
        <p className="mt-2 text-muted">Aucune opération pour le moment.</p>
      )}
      {items.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table aria-label="Opérations" className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Date</th>
                <th className="py-2 pr-4 font-medium">Opération</th>
                <th className="py-2 pr-4 font-medium">Effet sur la trésorerie</th>
                <th className="py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((transaction) => (
                <TransactionRow
                  key={transaction.id}
                  transaction={transaction}
                  instruments={byId}
                  currency={account.currency}
                  onEdit={(selected) => setPanel({ kind: 'edit', transaction: selected })}
                  onVoid={(selected) => cancel.mutate(selected)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {transactions.hasNextPage && (
        <button
          type="button"
          className={`${secondaryButtonClass} mt-3`}
          disabled={transactions.isFetchingNextPage}
          onClick={() => void transactions.fetchNextPage()}
        >
          Charger plus d’opérations
        </button>
      )}
    </section>
  )
}
