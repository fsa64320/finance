/**
 * SC-010 / FR-034 : aucun écran ne remonte de violation bloquante à l'audit automatisé (axe).
 * Les règles dépendant du rendu réel (contrastes) sont désactivées : jsdom ne calcule pas les
 * styles, le contraste est vérifié dans un vrai navigateur (T143).
 */
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import * as accountsApi from '../../src/api/accounts'
import * as dashboardApi from '../../src/api/dashboard'
import * as instrumentsApi from '../../src/api/instruments'
import * as transactionsApi from '../../src/api/transactions'
import AccountDetail from '../../src/pages/AccountDetail'
import Accounts from '../../src/pages/Accounts'
import Dashboard from '../../src/pages/Dashboard'
import Instruments from '../../src/pages/Instruments'
import Login from '../../src/pages/Login'
import {
  FUND_ID,
  LIVRET_ID,
  PEA_ID,
  allocationBody,
  detail,
  instrument,
  seriesBody,
  summary,
  summaryBody,
  transaction,
} from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/accounts')
vi.mock('../../src/api/dashboard')
vi.mock('../../src/api/instruments')
vi.mock('../../src/api/transactions')

const OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

async function expectNoViolations(container: HTMLElement) {
  const results = await axe(container, OPTIONS)
  const blocking = results.violations.map((v) => `${v.id}: ${v.help}`)
  expect(blocking).toEqual([])
}

beforeEach(() => {
  vi.mocked(dashboardApi.getSummary).mockResolvedValue(summaryBody() as never)
  vi.mocked(dashboardApi.getSeries).mockResolvedValue(seriesBody() as never)
  vi.mocked(dashboardApi.getAllocation).mockResolvedValue(allocationBody() as never)
  vi.mocked(accountsApi.listAccounts).mockResolvedValue([
    summary(),
    summary({ id: LIVRET_ID, type: 'LIVRET_A', name: 'Livret A' }),
  ])
  vi.mocked(accountsApi.getAccount).mockResolvedValue(detail())
  vi.mocked(instrumentsApi.listInstruments).mockResolvedValue([
    instrument(),
    instrument({ id: FUND_ID, kind: 'EURO_FUND', name: 'Fonds en euros', isin: undefined }),
  ])
  vi.mocked(transactionsApi.listTransactions).mockResolvedValue({
    items: [transaction()],
    next_cursor: null,
  } as never)
})

describe('audit d’accessibilité (axe)', () => {
  it('connexion : création du mot de passe', async () => {
    const { container } = render(<Login mode="setup" onSuccess={() => {}} />)
    await expectNoViolations(container)
  })

  it('connexion : déverrouillage', async () => {
    const { container } = render(<Login mode="unlock" onSuccess={() => {}} />)
    await expectNoViolations(container)
  })

  it('tableau de bord', async () => {
    const { container } = renderWithProviders(<Dashboard />)
    await screen.findByTestId('net-worth')
    await screen.findByRole('table', { name: /comptes/i })
    await expectNoViolations(container)
  })

  it('comptes', async () => {
    const { container } = renderWithProviders(<Accounts />)
    await screen.findByRole('table', { name: /comptes/i })
    await expectNoViolations(container)
  })

  it('détail de compte', async () => {
    const { container } = renderWithProviders(<AccountDetail />, {
      route: `/comptes/${PEA_ID}`,
      path: '/comptes/:accountId',
    })
    await screen.findByTestId('account-value')
    await expectNoViolations(container)
  })

  it('actifs', async () => {
    const { container } = renderWithProviders(<Instruments />)
    await screen.findByText('Fonds en euros')
    await expectNoViolations(container)
  })
})
