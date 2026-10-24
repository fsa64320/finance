import { request } from './client'
import type { LivretARate } from './types'

export function listLivretRates(): Promise<LivretARate[]> {
  return request<LivretARate[]>('GET', '/rates/livret-a')
}

export function addLivretRate(rate: LivretARate): Promise<LivretARate> {
  return request<LivretARate>('POST', '/rates/livret-a', rate)
}
