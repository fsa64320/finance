import { request } from './client'
import type { components, paths } from './schema'

export type DashboardSummary = components['schemas']['DashboardSummary']
type SeriesBody =
  paths['/dashboard/series']['get']['responses']['200']['content']['application/json']
type AllocationBody =
  paths['/dashboard/allocation']['get']['responses']['200']['content']['application/json']

export type SeriesPoint = SeriesBody['points'][number]
export type AllocationSlice = AllocationBody['slices'][number]
export type Period = '1m' | '3m' | '1y' | '5y' | 'all'

export function getSummary(asOf?: string): Promise<DashboardSummary> {
  const suffix = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  return request<DashboardSummary>('GET', `/dashboard/summary${suffix}`)
}

export function getSeries(period: Period): Promise<SeriesBody> {
  return request<SeriesBody>('GET', `/dashboard/series?period=${period}`)
}

export function getAllocation(asOf?: string): Promise<AllocationBody> {
  const suffix = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  return request<AllocationBody>('GET', `/dashboard/allocation${suffix}`)
}
