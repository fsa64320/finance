/**
 * FR-036 : chaque écran de données définit ses états vide, chargement, erreur et succès.
 * Le succès est annoncé par la région `aria-live` du `LiveAnnouncer` (FR-034).
 */
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import * as dashboardApi from '../../src/api/dashboard'
import * as instrumentsApi from '../../src/api/instruments'
import * as transactionsApi from '../../src/api/transactions'
import LiveAnnouncer from '../../src/components/LiveAnnouncer'
import AccountDetail from '../../src/pages/AccountDetail'
import Accounts from '../../src/pages/Accounts'
import Dashboard from '../../src/pages/Dashboard'
import Instruments from '../../src/pages/Instruments'
import { PEA_ID, account, allocationBody, instrument, seriesBody, summaryBody } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/accounts')
vi.mock('../../src/api/dashboard')
vi.mock('../../src/api/instruments')
vi.mock('../../src/api/transactions')

const never = new Promise<never>(() => {})
const failure = () => Promise.reject(new Error('panne'))

function inAnnouncer(ui: React.ReactElement, options?: Parameters<typeof renderWithProviders>[1]) {
  return renderWithProviders(<LiveAnnouncer>{ui}</LiveAnnouncer>, options)
}

beforeEach(() => {
  vi.mocked(dashboardApi.getSummary)
    .mockReset()
    .mockResolvedValue(summaryBody() as never)
  vi.mocked(dashboardApi.getSeries)
    .mockReset()
    .mockResolvedValue(seriesBody() as never)
  vi.mocked(dashboardApi.getAllocation)
    .mockReset()
    .mockResolvedValue(allocationBody() as never)
  vi.mocked(accountsApi.listAccounts).mockReset().mockResolvedValue([])
  vi.mocked(instrumentsApi.listInstruments).mockReset().mockResolvedValue([])
  vi.mocked(transactionsApi.listTransactions)
    .mockReset()
    .mockResolvedValue({ items: [], next_cursor: null } as never)
})

describe('tableau de bord', () => {
  it('chargement : état annoncé', () => {
    vi.mocked(dashboardApi.getSummary).mockReturnValue(never)
    inAnnouncer(<Dashboard />)
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
  })

  it('erreur : cause et nouvelle tentative', async () => {
    vi.mocked(dashboardApi.getSummary).mockImplementation(failure)
    inAnnouncer(<Dashboard />)
    expect(await screen.findByText('Impossible de charger le patrimoine.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })

  it('vide : guide vers la création d’un premier compte', async () => {
    inAnnouncer(<Dashboard />)
    expect(await screen.findByText('Commencez par créer un compte')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Créer un compte' })).toBeInTheDocument()
  })
})

describe('comptes', () => {
  it('chargement, erreur avec nouvelle tentative, vide', async () => {
    vi.mocked(accountsApi.listAccounts).mockReturnValueOnce(never)
    const { unmount } = inAnnouncer(<Accounts />)
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    unmount()

    vi.mocked(accountsApi.listAccounts).mockImplementationOnce(failure)
    const second = inAnnouncer(<Accounts />)
    expect(await screen.findByText('Impossible de charger les comptes.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    second.unmount()

    inAnnouncer(<Accounts />)
    expect(await screen.findByText(/Aucun compte pour le moment/)).toBeInTheDocument()
  })

  it('succès : la création est annoncée', async () => {
    vi.mocked(accountsApi.createAccount).mockResolvedValue(account())
    inAnnouncer(<Accounts />)
    await screen.findByText(/Aucun compte pour le moment/)
    await userEvent.type(screen.getByLabelText('Nom du compte'), 'PEA Courtier A')
    await userEvent.type(screen.getByLabelText("Date d'ouverture"), '2026-01-02')
    await userEvent.click(screen.getByRole('button', { name: 'Créer le compte' }))
    await waitFor(() => {
      const regions = screen.getAllByRole('status')
      expect(regions.some((r) => r.textContent?.includes('PEA Courtier A'))).toBe(true)
    })
  })
})

describe('actifs', () => {
  it('chargement, erreur avec nouvelle tentative, vide', async () => {
    vi.mocked(instrumentsApi.listInstruments).mockReturnValueOnce(never)
    const { unmount } = inAnnouncer(<Instruments />)
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    unmount()

    vi.mocked(instrumentsApi.listInstruments).mockImplementationOnce(failure)
    const second = inAnnouncer(<Instruments />)
    expect(await screen.findByText('Impossible de charger les actifs.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
    second.unmount()

    inAnnouncer(<Instruments />)
    expect(await screen.findByText(/Aucun actif pour le moment/)).toBeInTheDocument()
  })

  it('succès : l’ajout est annoncé', async () => {
    vi.mocked(instrumentsApi.createInstrument).mockResolvedValue(instrument())
    inAnnouncer(<Instruments />)
    await screen.findByText(/Aucun actif pour le moment/)
    await userEvent.type(screen.getByLabelText('Nom'), 'ETF Monde')
    await userEvent.click(screen.getByRole('button', { name: /Ajouter l.actif/ }))
    await waitFor(() => {
      const regions = screen.getAllByRole('status')
      expect(regions.some((r) => r.textContent?.includes('ETF Monde'))).toBe(true)
    })
  })
})

describe('détail de compte', () => {
  const show = () =>
    inAnnouncer(<AccountDetail />, { route: `/comptes/${PEA_ID}`, path: '/comptes/:accountId' })

  it('chargement', () => {
    vi.mocked(accountsApi.getAccount).mockReturnValue(never)
    show()
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
  })

  it('erreur : cause et nouvelle tentative', async () => {
    vi.mocked(accountsApi.getAccount).mockImplementation(failure)
    show()
    expect(await screen.findByText('Impossible de charger le compte.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })
})
