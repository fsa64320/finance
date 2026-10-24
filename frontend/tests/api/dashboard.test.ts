import { afterEach, describe, expect, it, vi } from 'vitest'

import * as client from '../../src/api/client'
import { getAllocation, getSeries, getSummary } from '../../src/api/dashboard'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('API du tableau de bord', () => {
  it('lit la synthèse, à une date si demandée', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ net_worth: '1' })
    await getSummary()
    await getSummary('2026-01-31')
    expect(spy).toHaveBeenNthCalledWith(1, 'GET', '/dashboard/summary')
    expect(spy).toHaveBeenNthCalledWith(2, 'GET', '/dashboard/summary?as_of=2026-01-31')
  })

  it('lit la série pour une période', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ points: [] })
    await getSeries('5y')
    expect(spy).toHaveBeenCalledWith('GET', '/dashboard/series?period=5y')
  })

  it('lit la répartition', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ slices: [] })
    await getAllocation()
    expect(spy).toHaveBeenCalledWith('GET', '/dashboard/allocation')
  })
})
