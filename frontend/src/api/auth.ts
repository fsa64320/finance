import type { paths } from './schema'
import { request } from './client'

type StatusBody = paths['/auth/status']['get']['responses']['200']['content']['application/json']

export type AuthState = StatusBody['state']

export const AUTH_STATUS_KEY = ['auth', 'status'] as const

export async function getAuthStatus(): Promise<AuthState> {
  const body = await request<StatusBody>('GET', '/auth/status')
  return body.state
}

export async function setupPassword(password: string): Promise<void> {
  await request('POST', '/auth/setup', { password })
}

export async function unlockInstance(password: string): Promise<void> {
  await request('POST', '/auth/unlock', { password })
}

export async function lockInstance(): Promise<void> {
  await request('POST', '/auth/lock')
}
