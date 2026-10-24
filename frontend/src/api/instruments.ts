import { request } from './client'
import type { Instrument, InstrumentInput } from './types'

export function listInstruments(): Promise<Instrument[]> {
  return request<Instrument[]>('GET', '/instruments')
}

export function createInstrument(input: InstrumentInput): Promise<Instrument> {
  return request<Instrument>('POST', '/instruments', input)
}
