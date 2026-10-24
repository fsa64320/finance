import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import * as authApi from '../../src/api/auth'
import * as dataApi from '../../src/api/data'
import * as ratesApi from '../../src/api/rates'
import * as settingsApi from '../../src/api/settings'
import Settings from '../../src/pages/Settings'
import { LIVRET_RATES, settingsBody } from '../fixtures'
import * as download from '../../src/lib/download'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/settings')
vi.mock('../../src/api/rates')
vi.mock('../../src/api/data')
vi.mock('../../src/api/auth')
vi.mock('../../src/lib/download')

beforeEach(() => {
  vi.mocked(dataApi.exportData).mockReset().mockResolvedValue({ format_version: 1 })
  vi.mocked(dataApi.restoreData).mockReset().mockResolvedValue(undefined)
  vi.mocked(authApi.changePassword).mockReset().mockResolvedValue(undefined)
  vi.mocked(download.downloadJson).mockReset()
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

describe('Sauvegarde et sécurité', () => {
  it('ajoute les sections sauvegarde et mot de passe', async () => {
    renderWithProviders(<Settings />)
    expect(
      await screen.findByRole('heading', { name: 'Sauvegarde et restauration' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Mot de passe' })).toBeInTheDocument()
  })

  it('exporte et télécharge le fichier nommé par la date', async () => {
    vi.mocked(dataApi.exportData).mockResolvedValue({
      format_version: 1,
      exported_at: '2026-10-24T12:00:00Z',
    })
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    await user.click(await screen.findByRole('button', { name: 'Exporter mes données' }))
    await waitFor(() =>
      expect(download.downloadJson).toHaveBeenCalledWith('finance-export-2026-10-24.json', {
        format_version: 1,
        exported_at: '2026-10-24T12:00:00Z',
      }),
    )
  })

  it('restaure le contenu du fichier choisi', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    const file = new File([JSON.stringify({ format_version: 1, accounts: [] })], 'export.json', {
      type: 'application/json',
    })
    await user.upload(await screen.findByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    const dialog = await screen.findByRole('dialog', { name: 'Restaurer ces données ?' })
    await user.click(within(dialog).getByRole('button', { name: 'Restaurer les données' }))
    await waitFor(() =>
      expect(dataApi.restoreData).toHaveBeenCalledWith({ format_version: 1, accounts: [] }),
    )
  })

  it('refuse un fichier qui n’est pas du JSON sans appeler le serveur', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    const file = new File(['pas du json'], 'export.json', { type: 'application/json' })
    await user.upload(await screen.findByLabelText('Fichier d’export à restaurer'), file)
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    const dialog = await screen.findByRole('dialog', { name: 'Restaurer ces données ?' })
    await user.click(within(dialog).getByRole('button', { name: 'Restaurer les données' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/n’est pas un export valide/i)
    expect(dataApi.restoreData).not.toHaveBeenCalled()
  })

  it('enregistre la fréquence du rappel d’export', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    const field = await screen.findByLabelText('Me rappeler d’exporter tous les (jours)')
    await user.clear(field)
    await user.type(field, '14')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le rappel' }))
    await waitFor(() =>
      expect(settingsApi.patchSettings).toHaveBeenCalledWith({ export_reminder_days: 14 }),
    )
  })

  it('change le mot de passe', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Settings />)
    await user.type(await screen.findByLabelText('Mot de passe actuel'), 'ancien-mot-de-passe-1')
    await user.type(screen.getByLabelText('Nouveau mot de passe'), 'nouveau-mot-de-passe-2')
    await user.type(
      screen.getByLabelText('Confirmer le nouveau mot de passe'),
      'nouveau-mot-de-passe-2',
    )
    await user.click(screen.getByRole('button', { name: 'Changer le mot de passe' }))
    const dialog = await screen.findByRole('dialog', { name: 'Changer le mot de passe ?' })
    await user.click(within(dialog).getByRole('button', { name: 'Changer le mot de passe' }))
    await waitFor(() =>
      expect(authApi.changePassword).toHaveBeenCalledWith(
        'ancien-mot-de-passe-1',
        'nouveau-mot-de-passe-2',
      ),
    )
  })
})
