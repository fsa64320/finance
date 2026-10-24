import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import { ApiError } from '../../src/api/client'
import * as dashboardApi from '../../src/api/dashboard'
import Dashboard from '../../src/pages/Dashboard'
import { LIVRET_ID, PEA_ID, allocationBody, seriesBody, summary, summaryBody } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/dashboard')
vi.mock('../../src/api/accounts')

const plain = (text: string | null) => (text ?? '').replace(/\s/g, ' ')

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
  vi.mocked(accountsApi.listAccounts)
    .mockReset()
    .mockResolvedValue([
      summary(),
      summary({
        id: LIVRET_ID,
        type: 'LIVRET_A',
        name: 'Livret A',
        value: '2500',
        estimated: true,
      }),
    ])
})

describe('synthèse', () => {
  it('affiche le patrimoine net avec la mention « hors dettes »', async () => {
    renderWithProviders(<Dashboard />)
    const net = await screen.findByTestId('net-worth')
    expect(plain(net.textContent)).toBe('8 500,00 €')
    expect(screen.getByText('hors dettes')).toBeInTheDocument()
  })

  it('indique la date de valorisation', async () => {
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText(/au 24\/10\/2026/)).toBeInTheDocument()
  })

  it('signale que la valeur est estimée et explique pourquoi', async () => {
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText('Valeur estimée')).toBeInTheDocument()
    expect(screen.getByText('Aucun prix connu : valorisé au prix de revient.')).toBeInTheDocument()
  })

  it('ne signale rien quand tout est à jour', async () => {
    vi.mocked(dashboardApi.getSummary).mockResolvedValue(
      summaryBody({ estimated: false, notices: [] }) as never,
    )
    renderWithProviders(<Dashboard />)
    await screen.findByTestId('net-worth')
    expect(screen.queryByText('Valeur estimée')).not.toBeInTheDocument()
  })

  it('dit quoi faire quand la synthèse ne se charge pas', async () => {
    vi.mocked(dashboardApi.getSummary).mockRejectedValue(
      new ApiError(500, 'internal_error', 'Erreur interne'),
    )
    renderWithProviders(<Dashboard />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/Impossible de charger le patrimoine/)
    expect(within(alert).getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })

  it('recharge la synthèse sur « Réessayer »', async () => {
    vi.mocked(dashboardApi.getSummary)
      .mockRejectedValueOnce(new ApiError(500, 'internal_error', 'Erreur interne'))
      .mockResolvedValue(summaryBody() as never)
    renderWithProviders(<Dashboard />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByTestId('net-worth')).toBeInTheDocument()
  })

  it('annonce le chargement', () => {
    vi.mocked(dashboardApi.getSummary).mockReturnValue(new Promise(() => {}) as never)
    renderWithProviders(<Dashboard />)
    expect(screen.getAllByText(/Chargement/).length).toBeGreaterThan(0)
  })
})

describe('évolution', () => {
  it('charge par défaut la période d’un an', async () => {
    renderWithProviders(<Dashboard />)
    await screen.findByRole('img', { name: /Évolution du patrimoine/ })
    expect(dashboardApi.getSeries).toHaveBeenCalledWith('1y')
    expect(screen.getByRole('button', { name: '1 an' })).toHaveAttribute('aria-pressed', 'true')
  })

  it.each([
    ['1 mois', '1m'],
    ['3 mois', '3m'],
    ['5 ans', '5y'],
    ['Tout', 'all'],
  ])('change de période avec « %s »', async (label, period) => {
    renderWithProviders(<Dashboard />)
    const user = userEvent.setup()
    await screen.findByRole('img', { name: /Évolution du patrimoine/ })
    await user.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(dashboardApi.getSeries).toHaveBeenCalledWith(period))
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '1 an' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('propose les cinq périodes dans un groupe nommé', async () => {
    renderWithProviders(<Dashboard />)
    const group = await screen.findByRole('group', { name: 'Période' })
    expect(within(group).getAllByRole('button')).toHaveLength(5)
  })

  it('dit quand il n’y a pas encore d’historique', async () => {
    vi.mocked(dashboardApi.getSeries).mockResolvedValue(seriesBody({ points: [] }) as never)
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText(/Pas encore d'historique à afficher/)).toBeInTheDocument()
  })

  it('signale une série qui ne se charge pas, sans bloquer le reste', async () => {
    vi.mocked(dashboardApi.getSeries).mockRejectedValue(
      new ApiError(500, 'internal_error', 'Erreur interne'),
    )
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText(/Impossible de charger l'évolution/)).toBeInTheDocument()
    expect(await screen.findByTestId('net-worth')).toBeInTheDocument()
  })
})

describe('répartition', () => {
  it('liste les classes d’actifs avec leur poids', async () => {
    renderWithProviders(<Dashboard />)
    const list = await screen.findByRole('list', { name: 'Répartition par classe d’actifs' })
    expect(
      plain(
        within(list)
          .getByText(/Fonds en euros/)
          .closest('li')!.textContent,
      ),
    ).toContain('58,82 %')
  })

  it('signale une répartition qui ne se charge pas', async () => {
    vi.mocked(dashboardApi.getAllocation).mockRejectedValue(
      new ApiError(500, 'internal_error', 'Erreur interne'),
    )
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText(/Impossible de charger la répartition/)).toBeInTheDocument()
  })
})

describe('comptes', () => {
  it('liste les comptes avec un lien vers leur détail', async () => {
    renderWithProviders(<Dashboard />)
    const link = await screen.findByRole('link', { name: 'PEA Courtier A' })
    expect(link).toHaveAttribute('href', `/comptes/${PEA_ID}`)
    expect(screen.getByRole('link', { name: 'Livret A' })).toBeInTheDocument()
  })

  it('renvoie vers la page Comptes', async () => {
    renderWithProviders(<Dashboard />)
    expect(await screen.findByRole('link', { name: 'Gérer mes comptes' })).toHaveAttribute(
      'href',
      '/comptes',
    )
  })

  it('guide vers la création d’un premier compte quand il n’y en a aucun', async () => {
    vi.mocked(accountsApi.listAccounts).mockResolvedValue([])
    vi.mocked(dashboardApi.getSummary).mockResolvedValue(
      summaryBody({ net_worth: '0', estimated: false, notices: [] }) as never,
    )
    vi.mocked(dashboardApi.getSeries).mockResolvedValue(seriesBody({ points: [] }) as never)
    vi.mocked(dashboardApi.getAllocation).mockResolvedValue(allocationBody({ slices: [] }) as never)
    renderWithProviders(<Dashboard />)
    expect(
      await screen.findByRole('heading', { name: /Commencez par créer un compte/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Créer un compte' })).toHaveAttribute(
      'href',
      '/comptes',
    )
    expect(screen.queryByRole('group', { name: 'Période' })).not.toBeInTheDocument()
  })

  it('signale des comptes qui ne se chargent pas', async () => {
    vi.mocked(accountsApi.listAccounts).mockRejectedValue(new Error('réseau'))
    renderWithProviders(<Dashboard />)
    expect(await screen.findByText(/Impossible de charger les comptes/)).toBeInTheDocument()
  })
})

describe('structure', () => {
  it('a un titre de page et des sections titrées', async () => {
    renderWithProviders(<Dashboard />)
    await screen.findByTestId('net-worth')
    expect(screen.getByRole('heading', { level: 2, name: 'Tableau de bord' })).toBeInTheDocument()
    for (const name of ['Évolution', 'Répartition', 'Comptes']) {
      expect(screen.getByRole('heading', { level: 3, name })).toBeInTheDocument()
    }
  })
})
