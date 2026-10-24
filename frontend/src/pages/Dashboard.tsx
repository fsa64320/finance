import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { listAccounts } from '../api/accounts'
import { type Period, getAllocation, getSeries, getSummary } from '../api/dashboard'
import { keys } from '../api/keys'
import AccountList from '../components/AccountList'
import AllocationChart from '../components/AllocationChart'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import NetWorthChart from '../components/NetWorthChart'
import { formatDate, formatMoney } from '../lib/format'

const PERIODS: { value: Period; label: string }[] = [
  { value: '1m', label: '1 mois' },
  { value: '3m', label: '3 mois' },
  { value: '1y', label: '1 an' },
  { value: '5y', label: '5 ans' },
  { value: 'all', label: 'Tout' },
]

const cardClass = 'rounded-2xl border border-line bg-card p-5 shadow-sm'

export default function Dashboard() {
  const [period, setPeriod] = useState<Period>('1y')
  const summary = useQuery({ queryKey: keys.dashboardSummary, queryFn: () => getSummary() })
  const series = useQuery({
    queryKey: keys.dashboardSeries(period),
    queryFn: () => getSeries(period),
  })
  const allocation = useQuery({
    queryKey: keys.dashboardAllocation,
    queryFn: () => getAllocation(),
  })
  const accounts = useQuery({
    queryKey: keys.accountList(false),
    queryFn: () => listAccounts({ includeClosed: false }),
  })

  const noAccount = accounts.data !== undefined && accounts.data.length === 0

  return (
    <section>
      <h2 className="text-xl font-semibold">Tableau de bord</h2>

      <div className={`${cardClass} mt-4`}>
        {summary.isPending && <LoadingState />}
        {summary.isError && (
          <ErrorState
            message="Impossible de charger le patrimoine."
            onRetry={() => void summary.refetch()}
          />
        )}
        {summary.data && (
          <>
            <p className="text-sm text-muted">Patrimoine net</p>
            <p data-testid="net-worth" className="mt-1 text-4xl font-semibold">
              {formatMoney(summary.data.net_worth, summary.data.currency)}
            </p>
            <p className="mt-1 text-sm text-muted">
              <span>hors dettes</span> ·{' '}
              {summary.data.as_of && <>au {formatDate(summary.data.as_of)}</>}
            </p>
            {summary.data.estimated && (
              <div className="mt-3">
                <span className="rounded bg-warn-bg px-2 py-0.5 text-xs text-warn-ink">
                  Valeur estimée
                </span>
                <ul className="mt-2 list-disc pl-5 text-sm text-warn-ink">
                  {summary.data.notices.map((notice, index) => (
                    <li
                      key={`${notice.kind}-${notice.account_id ?? ''}-${notice.instrument_id ?? ''}-${index}`}
                    >
                      {notice.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      {noAccount ? (
        <div className="mt-6">
          <EmptyState />
        </div>
      ) : (
        <>
          <div className={`${cardClass} mt-6`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-medium">Évolution</h3>
              <div role="group" aria-label="Période" className="flex flex-wrap gap-1">
                {PERIODS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    aria-pressed={period === item.value}
                    onClick={() => setPeriod(item.value)}
                    className={`rounded-lg px-3 py-1.5 text-sm ${
                      period === item.value
                        ? 'bg-brand text-brand-ink'
                        : 'border border-line text-ink'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-4">
              {series.isPending && <LoadingState />}
              {series.isError && (
                <ErrorState
                  message="Impossible de charger l'évolution."
                  onRetry={() => void series.refetch()}
                />
              )}
              {series.data && (
                <NetWorthChart points={series.data.points} currency={series.data.currency} />
              )}
            </div>
          </div>

          <div className={`${cardClass} mt-6`}>
            <h3 className="font-medium">Répartition</h3>
            <div className="mt-4">
              {allocation.isPending && <LoadingState />}
              {allocation.isError && (
                <ErrorState
                  message="Impossible de charger la répartition."
                  onRetry={() => void allocation.refetch()}
                />
              )}
              {allocation.data && (
                <AllocationChart
                  slices={allocation.data.slices}
                  currency={allocation.data.currency}
                />
              )}
            </div>
          </div>
        </>
      )}

      {!noAccount && (
        <div className={`${cardClass} mt-6`}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-medium">Comptes</h3>
            <Link className="text-sm text-brand underline" to="/comptes">
              Gérer mes comptes
            </Link>
          </div>
          <div className="mt-4">
            {accounts.isPending && <LoadingState />}
            {accounts.isError && (
              <ErrorState
                message="Impossible de charger les comptes."
                onRetry={() => void accounts.refetch()}
              />
            )}
            {accounts.data && <AccountList accounts={accounts.data} />}
          </div>
        </div>
      )}
    </section>
  )
}
