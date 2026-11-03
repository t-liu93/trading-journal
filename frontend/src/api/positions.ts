import type { components } from './schema'
import { http } from './http'
import { utcTimestamp } from './datetimes'

export type Position = components['schemas']['PositionRead']
export type PositionCreate = components['schemas']['PositionCreate']
export type PositionUpdate = components['schemas']['PositionUpdate']
export type PositionStatus = components['schemas']['PositionStatus']
export type StrategyType = components['schemas']['StrategyType']

function readPosition(value: unknown): Position {
  const position = value as Position
  return { ...position, opened_at: utcTimestamp(position.opened_at),
    closed_at: position.closed_at === null ? null : utcTimestamp(position.closed_at) }
}

export const positionsApi = {
  list: (params?: { status?: PositionStatus; strategy_type?: StrategyType; limit?: number }) =>
    http.get(`/api/positions${buildQuery(params)}`).then(value => (value as Position[]).map(readPosition)),
  get: (id: string) => http.get(`/api/positions/${id}`).then(readPosition),
  create: (payload: PositionCreate) =>
    http.post('/api/positions', payload).then(readPosition),
  update: (id: string, payload: PositionUpdate) =>
    http.patch(`/api/positions/${id}`, payload).then(readPosition),
  remove: (id: string) => http.delete(`/api/positions/${id}`) as Promise<null>,
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${qs.toString()}`
}
