import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request } from '../../src/api/client'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

const json = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json' },
    ...init,
  })

describe('request', () => {
  it('appelle /api/v1 avec les cookies de même origine', async () => {
    fetchMock.mockResolvedValue(json({ state: 'locked' }))
    await request('GET', '/auth/status')
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/auth/status')
    expect(options.method).toBe('GET')
    expect(options.credentials).toBe('same-origin')
  })

  it('renvoie le JSON de la réponse', async () => {
    fetchMock.mockResolvedValue(json({ state: 'unlocked' }))
    await expect(request('GET', '/auth/status')).resolves.toEqual({ state: 'unlocked' })
  })

  it('renvoie undefined sur une réponse 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(request('POST', '/auth/lock')).resolves.toBeUndefined()
  })

  it('envoie le corps en JSON', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await request('POST', '/auth/unlock', { password: 'secret-de-test' })
    const options = fetchMock.mock.calls[0][1]
    expect(options.headers['content-type']).toBe('application/json')
    expect(options.body).toBe(JSON.stringify({ password: 'secret-de-test' }))
  })

  it("traduit une erreur de l'API en ApiError", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          code: 'weak_password',
          message: 'Mot de passe refusé',
          details: [{ field: 'password', message: 'trop courant' }],
        },
        { status: 422 },
      ),
    )
    const error = await request('POST', '/auth/setup', { password: 'x' }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 422,
      code: 'weak_password',
      details: [{ field: 'password', message: 'trop courant' }],
    })
  })

  it('lit Retry-After sur un 429', async () => {
    fetchMock.mockResolvedValue(
      json(
        { code: 'too_many_attempts', message: "Trop d'essais" },
        { status: 429, headers: { 'retry-after': '30', 'content-type': 'application/json' } },
      ),
    )
    const error = (await request('POST', '/auth/unlock', { password: 'x' }).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(error.retryAfter).toBe(30)
  })

  it("garde un code générique si le corps d'erreur n'est pas du JSON", async () => {
    fetchMock.mockResolvedValue(new Response('Bad gateway', { status: 502 }))
    const error = (await request('GET', '/auth/status').catch((e: unknown) => e)) as ApiError
    expect(error).toMatchObject({ status: 502, code: 'http_error' })
  })

  it('signale une panne réseau', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = (await request('GET', '/auth/status').catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, code: 'network_error' })
  })
})
