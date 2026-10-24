import { afterEach, describe, expect, it, vi } from 'vitest'

import { changePassword } from '../../src/api/auth'
import * as client from '../../src/api/client'
import { exportData, restoreData } from '../../src/api/data'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('API des données', () => {
  it('exporte toutes les données', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ format_version: 1 })
    await expect(exportData()).resolves.toEqual({ format_version: 1 })
    expect(spy).toHaveBeenCalledWith('GET', '/data/export')
  })

  it('restaure un export tel quel', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue(undefined)
    const payload = { format_version: 1, accounts: [] }
    await restoreData(payload)
    expect(spy).toHaveBeenCalledWith('POST', '/data/restore', payload)
  })

  it('change le mot de passe', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue(undefined)
    await changePassword('ancien-mot-de-passe-1', 'nouveau-mot-de-passe-2')
    expect(spy).toHaveBeenCalledWith('POST', '/auth/change-password', {
      current_password: 'ancien-mot-de-passe-1',
      new_password: 'nouveau-mot-de-passe-2',
    })
  })
})
