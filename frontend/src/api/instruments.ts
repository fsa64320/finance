import { request } from './client'
import type { Instrument, InstrumentInput, TickerSuggestion } from './types'

export function listInstruments(): Promise<Instrument[]> {
  return request<Instrument[]>('GET', '/instruments')
}

export function createInstrument(input: InstrumentInput): Promise<Instrument> {
  return request<Instrument>('POST', '/instruments', input)
}

export function updateInstrument(
  instrumentId: string,
  patch: { name?: string; price_ticker?: string; price_mode?: 'AUTO' | 'MANUAL' },
): Promise<Instrument> {
  return request<Instrument>('PATCH', `/instruments/${instrumentId}`, patch)
}

/** Demande à OpenFIGI des tickers pour l'ISIN de l'actif ; seul l'ISIN part, à la demande. */
export function suggestTickers(instrumentId: string): Promise<TickerSuggestion[]> {
  return request<TickerSuggestion[]>('POST', `/instruments/${instrumentId}/ticker-suggestions`)
}
