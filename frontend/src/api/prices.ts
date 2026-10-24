import { request } from './client'
import type { Price, PriceInput, RefreshResult } from './types'

export function listPrices(instrumentId: string): Promise<Price[]> {
  return request<Price[]>('GET', `/prices?instrument_id=${encodeURIComponent(instrumentId)}`)
}

export function addPrice(input: PriceInput): Promise<Price> {
  return request<Price>('POST', '/prices', input)
}

/** Met à jour cours et taux ; sans effet si la récupération automatique est désactivée. */
export function refreshPrices(): Promise<RefreshResult> {
  return request<RefreshResult>('POST', '/prices/refresh')
}
