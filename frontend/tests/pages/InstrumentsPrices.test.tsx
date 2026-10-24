import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import * as instrumentsApi from '../../src/api/instruments'
import * as pricesApi from '../../src/api/prices'
import Instruments from '../../src/pages/Instruments'
import { ETF_ID, FUND_ID, instrument, priceBody } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/instruments')
vi.mock('../../src/api/prices')

const SCPI_ID = '88888888-8888-4888-8888-888888888888'

beforeEach(() => {
  vi.mocked(instrumentsApi.listInstruments)
    .mockReset()
    .mockResolvedValue([
      instrument({ price_ticker: 'CW8.PA' }),
      instrument({
        id: SCPI_ID,
        kind: 'SCPI',
        name: 'SCPI Exemple',
        isin: undefined,
        price_mode: 'MANUAL',
      }),
      instrument({
        id: FUND_ID,
        kind: 'EURO_FUND',
        name: 'Fonds en euros',
        isin: undefined,
        price_mode: 'MANUAL',
      }),
    ])
  vi.mocked(instrumentsApi.updateInstrument).mockReset().mockResolvedValue(instrument())
  vi.mocked(instrumentsApi.suggestTickers)
    .mockReset()
    .mockResolvedValue([{ ticker: 'CW8.PA', exchange: 'FP', name: 'AMUNDI MSCI WORLD' }])
  vi.mocked(pricesApi.listPrices)
    .mockReset()
    .mockResolvedValue([priceBody() as never])
  vi.mocked(pricesApi.addPrice)
    .mockReset()
    .mockResolvedValue(priceBody() as never)
  vi.mocked(pricesApi.refreshPrices)
    .mockReset()
    .mockResolvedValue({
      sources: [
        { source: 'ecb', status: 'ok', updated: 2 },
        { source: 'yahoo', status: 'ok', updated: 5 },
      ],
    } as never)
})

async function open(name: string) {
  const user = userEvent.setup()
  renderWithProviders(<Instruments />)
  await user.click(await screen.findByRole('button', { name: `Gérer ${name}` }))
  return user
}

describe('mise à jour des cours', () => {
  it('lance la mise à jour et résume chaque source', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Instruments />)
    await user.click(await screen.findByRole('button', { name: 'Mettre à jour les cours' }))
    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('BCE : 2 mises à jour')
    expect(status).toHaveTextContent('Yahoo Finance : 5 mises à jour')
  })

  it('renvoie vers les réglages quand la récupération est désactivée', async () => {
    vi.mocked(pricesApi.refreshPrices).mockResolvedValue({
      sources: [
        { source: 'ecb', status: 'disabled' },
        { source: 'yahoo', status: 'disabled' },
      ],
    } as never)
    const user = userEvent.setup()
    renderWithProviders(<Instruments />)
    await user.click(await screen.findByRole('button', { name: 'Mettre à jour les cours' }))
    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent(/désactivée/i)
    expect(within(status).getByRole('link', { name: 'Activer dans les réglages' })).toHaveAttribute(
      'href',
      '/reglages',
    )
  })

  it('explique un échec et rassure sur les prix déjà connus', async () => {
    vi.mocked(pricesApi.refreshPrices).mockResolvedValue({
      sources: [
        { source: 'ecb', status: 'ok', updated: 0 },
        { source: 'yahoo', status: 'failed', message: 'Yahoo Finance indisponible' },
      ],
    } as never)
    const user = userEvent.setup()
    renderWithProviders(<Instruments />)
    await user.click(await screen.findByRole('button', { name: 'Mettre à jour les cours' }))
    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('Yahoo Finance indisponible')
    expect(status).toHaveTextContent(/derniers prix connus/i)
  })

  it('signale un résultat partiel', async () => {
    vi.mocked(pricesApi.refreshPrices).mockResolvedValue({
      sources: [
        { source: 'yahoo', status: 'partial', updated: 1, message: 'Pas de cours pour : BAD.PA.' },
      ],
    } as never)
    const user = userEvent.setup()
    renderWithProviders(<Instruments />)
    await user.click(await screen.findByRole('button', { name: 'Mettre à jour les cours' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Pas de cours pour : BAD.PA.')
  })

  it('affiche une erreur réseau', async () => {
    vi.mocked(pricesApi.refreshPrices).mockRejectedValue(new Error('réseau'))
    const user = userEvent.setup()
    renderWithProviders(<Instruments />)
    await user.click(await screen.findByRole('button', { name: 'Mettre à jour les cours' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/mise à jour/i)
  })

  it('montre le ticker de chaque actif dans la liste', async () => {
    renderWithProviders(<Instruments />)
    const table = await screen.findByRole('table', { name: 'Actifs' })
    const etf = within(table).getByText('ETF Monde').closest('tr')!
    expect(within(etf).getByText('CW8.PA')).toBeInTheDocument()
  })
})

describe('ticker', () => {
  it('enregistre le ticker saisi', async () => {
    const user = await open('ETF Monde')
    const field = screen.getByLabelText('Ticker de cotation de cet actif')
    expect(field).toHaveValue('CW8.PA')
    await user.clear(field)
    await user.type(field, 'IWDA.AS')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le ticker' }))
    expect(instrumentsApi.updateInstrument).toHaveBeenCalledWith(ETF_ID, {
      price_ticker: 'IWDA.AS',
    })
  })

  it('propose des tickers à partir de l’ISIN et en retient un', async () => {
    const user = await open('ETF Monde')
    await user.click(screen.getByRole('button', { name: 'Chercher un ticker' }))
    expect(instrumentsApi.suggestTickers).toHaveBeenCalledWith(ETF_ID)
    expect(await screen.findByText(/AMUNDI MSCI WORLD/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Utiliser CW8.PA' }))
    expect(instrumentsApi.updateInstrument).toHaveBeenCalledWith(ETF_ID, { price_ticker: 'CW8.PA' })
  })

  it('dit quand la recherche est impossible tant que la récupération est désactivée', async () => {
    vi.mocked(instrumentsApi.suggestTickers).mockRejectedValue(
      new ApiError(409, 'conflict', 'La récupération automatique est désactivée.'),
    )
    const user = await open('ETF Monde')
    await user.click(screen.getByRole('button', { name: 'Chercher un ticker' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La récupération automatique est désactivée.',
    )
    expect(screen.getByRole('link', { name: 'Activer dans les réglages' })).toBeInTheDocument()
  })

  it('dit quand OpenFIGI est indisponible', async () => {
    vi.mocked(instrumentsApi.suggestTickers).mockRejectedValue(
      new ApiError(502, 'external_source_failed', 'OpenFIGI indisponible'),
    )
    const user = await open('ETF Monde')
    await user.click(screen.getByRole('button', { name: 'Chercher un ticker' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('OpenFIGI indisponible')
  })

  it('dit quand aucun ticker n’est trouvé', async () => {
    vi.mocked(instrumentsApi.suggestTickers).mockResolvedValue([])
    const user = await open('ETF Monde')
    await user.click(screen.getByRole('button', { name: 'Chercher un ticker' }))
    expect(await screen.findByText(/Aucun ticker trouvé/)).toBeInTheDocument()
  })

  it('ne propose pas de recherche sans code ISIN', async () => {
    await open('SCPI Exemple')
    expect(screen.queryByRole('button', { name: 'Chercher un ticker' })).not.toBeInTheDocument()
  })
})

describe('prix', () => {
  it('liste les derniers prix connus avec leur source', async () => {
    await open('ETF Monde')
    const table = await screen.findByRole('table', { name: 'Derniers prix' })
    expect(within(table).getByText('20/10/2026')).toBeInTheDocument()
    expect(within(table).getByText('Saisi')).toBeInTheDocument()
    expect(pricesApi.listPrices).toHaveBeenCalledWith(ETF_ID)
  })

  it('saisit un cours à la main', async () => {
    const user = await open('ETF Monde')
    await user.type(await screen.findByLabelText('Date du prix'), '2026-10-21')
    await user.type(screen.getByLabelText('Cours (EUR)'), '99,5')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() =>
      expect(pricesApi.addPrice).toHaveBeenCalledWith({
        instrument_id: ETF_ID,
        price_date: '2026-10-21',
        kind: 'MARKET',
        value: '99.5',
        currency: 'EUR',
      }),
    )
  })

  it('saisit les deux prix d’une SCPI', async () => {
    const user = await open('SCPI Exemple')
    await user.type(await screen.findByLabelText('Date du prix'), '2026-10-21')
    await user.type(screen.getByLabelText('Prix de souscription (EUR)'), '250')
    await user.type(screen.getByLabelText('Prix de retrait (EUR)'), '225')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(pricesApi.addPrice).toHaveBeenCalledTimes(2))
    expect(vi.mocked(pricesApi.addPrice).mock.calls.map(([input]) => input.kind)).toEqual([
      'SUBSCRIPTION',
      'REDEMPTION',
    ])
  })

  it('n’offre pas de prix pour un fonds en euros', async () => {
    await open('Fonds en euros')
    expect(screen.getByText(/solde déclaré/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Date du prix')).not.toBeInTheDocument()
  })
})
