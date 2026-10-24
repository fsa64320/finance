import { request } from './client'
import type { Settings, SettingsPatch } from './types'

export function getSettings(): Promise<Settings> {
  return request<Settings>('GET', '/settings')
}

export function patchSettings(patch: SettingsPatch): Promise<Settings> {
  return request<Settings>('PATCH', '/settings', patch)
}
