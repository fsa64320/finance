import { afterEach, describe, expect, it, vi } from 'vitest'

import * as client from '../../src/api/client'
import { suggestTickers, updateInstrument } from '../../src/api/instruments'
import { addPrice, listPrices, refreshPrices } from '../../src/api/prices'
import { addLivretRate, listLivretRates } from '../../src/api/rates'
import { getSettings, patchSettings } from '../../src/api/settings'
import { ETF_ID } from '../fixtures'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('prix', () => {
  it('liste les prix d’un actif', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue([])
    await listPrices(ETF_ID)
    expect(spy).toHaveBeenCalledWith('GET', `/prices?instrument_id=${ETF_ID}`)
  })

  it('saisit un prix', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    const input = {
      instrument_id: ETF_ID,
      price_date: '2026-10-20',
      kind: 'MARKET',
      value: '1',
      currency: 'EUR',
    } as const
    await addPrice(input)
    expect(spy).toHaveBeenCalledWith('POST', '/prices', input)
  })

  it('lance la mise à jour', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ sources: [] })
    await refreshPrices()
    expect(spy).toHaveBeenCalledWith('POST', '/prices/refresh')
  })
})

describe('actifs', () => {
  it('modifie le ticker', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    await updateInstrument(ETF_ID, { price_ticker: 'CW8.PA' })
    expect(spy).toHaveBeenCalledWith('PATCH', `/instruments/${ETF_ID}`, { price_ticker: 'CW8.PA' })
  })

  it('demande des suggestions de ticker', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue([])
    await suggestTickers(ETF_ID)
    expect(spy).toHaveBeenCalledWith('POST', `/instruments/${ETF_ID}/ticker-suggestions`)
  })
})

describe('taux et réglages', () => {
  it('lit et ajoute les taux du Livret A', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue([])
    await listLivretRates()
    await addLivretRate({ effective_from: '2026-02-01', value: '1.5' })
    expect(spy).toHaveBeenNthCalledWith(1, 'GET', '/rates/livret-a')
    expect(spy).toHaveBeenNthCalledWith(2, 'POST', '/rates/livret-a', {
      effective_from: '2026-02-01',
      value: '1.5',
    })
  })

  it('lit et modifie les réglages', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    await getSettings()
    await patchSettings({ auto_fetch_prices: true })
    expect(spy).toHaveBeenNthCalledWith(1, 'GET', '/settings')
    expect(spy).toHaveBeenNthCalledWith(2, 'PATCH', '/settings', { auto_fetch_prices: true })
  })
})
