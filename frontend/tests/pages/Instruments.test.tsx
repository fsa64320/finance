import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as instrumentsApi from '../../src/api/instruments'
import { ApiError } from '../../src/api/client'
import Instruments from '../../src/pages/Instruments'
import { FUND_ID, instrument } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/instruments')

beforeEach(() => {
  vi.mocked(instrumentsApi.listInstruments)
    .mockReset()
    .mockResolvedValue([
      instrument(),
      instrument({
        id: FUND_ID,
        kind: 'EURO_FUND',
        name: 'Fonds en euros',
        isin: undefined,
        price_mode: 'MANUAL',
      }),
    ])
  vi.mocked(instrumentsApi.createInstrument).mockReset().mockResolvedValue(instrument())
})

describe('liste des actifs', () => {
  it('affiche nom, type, ISIN, devise et mode de prix', async () => {
    renderWithProviders(<Instruments />)
    const table = await screen.findByRole('table', { name: 'Actifs' })
    const etf = within(table).getByText('ETF Monde').closest('tr')!
    expect(within(etf).getByText('ETF')).toBeInTheDocument()
    expect(within(etf).getByText('IE00B4L5Y983')).toBeInTheDocument()
    expect(within(etf).getByText('EUR')).toBeInTheDocument()
    expect(within(etf).getByText('Automatique')).toBeInTheDocument()
    const fund = within(table).getByRole('rowheader', { name: 'Fonds en euros' }).closest('tr')!
    expect(
      within(fund).getByText('Fonds en euros', { selector: 'td:nth-child(2)' }),
    ).toBeInTheDocument()
    expect(within(fund).getByText('Saisie manuelle')).toBeInTheDocument()
  })

  it('invite à créer un premier actif quand la liste est vide', async () => {
    vi.mocked(instrumentsApi.listInstruments).mockResolvedValue([])
    renderWithProviders(<Instruments />)
    expect(await screen.findByText(/Aucun actif pour le moment/)).toBeInTheDocument()
  })

  it('signale une erreur de chargement', async () => {
    vi.mocked(instrumentsApi.listInstruments).mockRejectedValue(new Error('réseau'))
    renderWithProviders(<Instruments />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Impossible de charger/)
  })
})

describe('création', () => {
  async function fill(user: ReturnType<typeof userEvent.setup>, isin = 'IE00B4L5Y983') {
    await screen.findByRole('table', { name: 'Actifs' })
    await user.selectOptions(screen.getByLabelText("Type d'actif"), 'ETF')
    await user.type(screen.getByLabelText('Nom'), 'ETF Europe')
    if (isin) await user.type(screen.getByLabelText('Code ISIN'), isin)
  }

  it('crée un actif en omettant les champs vides, puis recharge la liste', async () => {
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await fill(user, 'ie00b4l5y983')
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    await waitFor(() => expect(instrumentsApi.createInstrument).toHaveBeenCalledOnce())
    expect(vi.mocked(instrumentsApi.createInstrument).mock.calls[0]?.[0]).toEqual({
      kind: 'ETF',
      name: 'ETF Europe',
      isin: 'IE00B4L5Y983',
      currency: 'EUR',
    })
    await waitFor(() => expect(instrumentsApi.listInstruments).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText('Nom')).toHaveValue('')
  })

  it('envoie le ticker quand il est saisi', async () => {
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await fill(user, '')
    await user.type(screen.getByLabelText('Ticker de cotation'), 'CW8.PA')
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    await waitFor(() => expect(instrumentsApi.createInstrument).toHaveBeenCalledOnce())
    expect(vi.mocked(instrumentsApi.createInstrument).mock.calls[0]?.[0]).toMatchObject({
      price_ticker: 'CW8.PA',
    })
  })

  it('exige un nom', async () => {
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Actifs' })
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    expect(await screen.findByText("Le nom de l'actif est obligatoire.")).toBeInTheDocument()
    expect(instrumentsApi.createInstrument).not.toHaveBeenCalled()
  })

  it('refuse un ISIN mal formé avant tout appel', async () => {
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await fill(user, 'IE00')
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    expect(await screen.findByText(/Un ISIN fait 12 caractères/)).toBeInTheDocument()
    expect(instrumentsApi.createInstrument).not.toHaveBeenCalled()
  })

  it("affiche le message du serveur quand la clé de contrôle de l'ISIN est fausse", async () => {
    vi.mocked(instrumentsApi.createInstrument).mockRejectedValue(
      new ApiError(422, 'validation_error', 'Données invalides', [
        {
          field: 'isin',
          message: 'Code ISIN invalide : 12 caractères avec une clé de contrôle correcte.',
        },
      ]),
    )
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await fill(user, 'IE00B4L5Y984')
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    expect(await screen.findByText(/clé de contrôle correcte/)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByLabelText('Code ISIN')).toHaveAccessibleDescription(/clé de contrôle/),
    )
  })

  it('signale un ISIN déjà utilisé', async () => {
    vi.mocked(instrumentsApi.createInstrument).mockRejectedValue(
      new ApiError(409, 'conflict', 'Un actif porte déjà l’ISIN IE00B4L5Y983.'),
    )
    renderWithProviders(<Instruments />)
    const user = userEvent.setup()
    await fill(user)
    await user.click(screen.getByRole('button', { name: "Ajouter l'actif" }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/porte déjà l’ISIN/)
  })

  it('propose les sept types d’actif', async () => {
    renderWithProviders(<Instruments />)
    await screen.findByRole('table', { name: 'Actifs' })
    expect(within(screen.getByLabelText("Type d'actif")).getAllByRole('option')).toHaveLength(7)
  })
})
