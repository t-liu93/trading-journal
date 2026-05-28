import type { components } from './schema'
import { http } from './http'

export type Position = components['schemas']['PositionRead']
export type PositionCreate = components['schemas']['PositionCreate']
export type PositionUpdate = components['schemas']['PositionUpdate']
export type PositionStatus = components['schemas']['PositionStatus']
export type StrategyType = components['schemas']['StrategyType']

export const positionsApi = {
  list: (params?: { status?: PositionStatus; strategy_type?: StrategyType; limit?: number }) =>
    http.get(`/api/positions${buildQuery(params)}`) as Promise<Position[]>,
  get: (id: string) => http.get(`/api/positions/${id}`) as Promise<Position>,
  create: (payload: PositionCreate) =>
    http.post('/api/positions', payload) as Promise<Position>,
  update: (id: string, payload: PositionUpdate) =>
    http.patch(`/api/positions/${id}`, payload) as Promise<Position>,
  remove: (id: string) => http.delete(`/api/positions/${id}`) as Promise<null>,
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${qs.toString()}`
}
