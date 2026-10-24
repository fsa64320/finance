import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import * as ratesApi from '../../src/api/rates'
import * as settingsApi from '../../src/api/settings'
import Settings from '../../src/pages/Settings'
import { LIVRET_RATES, settingsBody } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/settings')
vi.mock('../../src/api/rates')

beforeEach(() => {
  vi.mocked(settingsApi.getSettings)
    .mockReset()
    .mockResolvedValue(settingsBody() as never)
  vi.mocked(settingsApi.patchSettings)
    .mockReset()
    .mockResolvedValue(settingsBody({ auto_fetch_prices: true }) as never)
  vi.mocked(ratesApi.listLivretRates).mockReset().mockResolvedValue(LIVRET_RATES)
  vi.mocked(ratesApi.addLivretRate).mockReset().mockResolvedValue(LIVRET_RATES[0]!)
})

describe('Réglages', () => {
  it('a un titre et deux sections', async () => {
    renderWithProviders(<Settings />)
    expect(screen.getByRole('heading', { level: 2, name: 'Réglages' })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Cours et taux automatiques' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Taux du Livret A' })).toBeInTheDocument()
  })

  it('montre la récupération désactivée par défaut', async () => {
    renderWithProviders(<Settings />)
    expect(await screen.findByRole('status')).toHaveTextContent(/désactivée/i)
  })

  it('active la récupération sur choix explicite', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    await user.click(
      await screen.findByRole('button', { name: 'Activer la récupération automatique' }),
    )
    await waitFor(() =>
      expect(settingsApi.patchSettings).toHaveBeenCalledWith({ auto_fetch_prices: true }),
    )
  })

  it('liste les taux et en ajoute un', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    expect(await screen.findByRole('table', { name: 'Taux du Livret A' })).toBeInTheDocument()
    await user.type(screen.getByLabelText("Date d'effet"), '2026-02-01')
    await user.type(screen.getByLabelText('Taux annuel (%)'), '1,5')
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    await waitFor(() =>
      expect(ratesApi.addLivretRate).toHaveBeenCalledWith({
        effective_from: '2026-02-01',
        value: '1.5',
      }),
    )
  })

  it('affiche l’erreur du serveur à l’ajout d’un taux', async () => {
    vi.mocked(ratesApi.addLivretRate).mockRejectedValue(
      new ApiError(422, 'validation_error', 'Données invalides', [
        { field: 'value', message: 'Le taux est un pourcentage entre 0 et 100.' },
      ]),
    )
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    await screen.findByRole('table', { name: 'Taux du Livret A' })
    await user.type(screen.getByLabelText("Date d'effet"), '2026-02-01')
    await user.type(screen.getByLabelText('Taux annuel (%)'), '5')
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    expect(
      await screen.findByText('Le taux est un pourcentage entre 0 et 100.'),
    ).toBeInTheDocument()
  })

  it('signale des réglages qui ne se chargent pas', async () => {
    vi.mocked(settingsApi.getSettings).mockRejectedValue(new Error('réseau'))
    renderWithProviders(<Settings />)
    expect(await screen.findByText(/Impossible de charger les réglages/)).toBeInTheDocument()
  })
})
