import { afterEach, describe, expect, it, vi } from 'vitest'

import * as client from '../../src/api/client'
import { getAuthStatus, lockInstance, setupPassword, unlockInstance } from '../../src/api/auth'

afterEach(() => {
  vi.restoreAllMocks()
})

describe("API d'authentification", () => {
  it("lit l'état de l'instance", async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({ state: 'locked' })
    await expect(getAuthStatus()).resolves.toBe('locked')
    expect(spy).toHaveBeenCalledWith('GET', '/auth/status')
  })

  it('crée le mot de passe', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue(undefined)
    await setupPassword('une-phrase-de-passe-1')
    expect(spy).toHaveBeenCalledWith('POST', '/auth/setup', { password: 'une-phrase-de-passe-1' })
  })

  it('déverrouille', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue(undefined)
    await unlockInstance('une-phrase-de-passe-1')
    expect(spy).toHaveBeenCalledWith('POST', '/auth/unlock', { password: 'une-phrase-de-passe-1' })
  })

  it('verrouille', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue(undefined)
    await lockInstance()
    expect(spy).toHaveBeenCalledWith('POST', '/auth/lock')
  })
})
