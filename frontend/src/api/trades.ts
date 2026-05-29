import type { components } from './schema'
import { http } from './http'

export type Trade        = components['schemas']['TradeRead']
export type TradeCreate  = components['schemas']['TradeCreate']
export type TradeUpdate  = components['schemas']['TradeUpdate']
export type TradeAction  = components['schemas']['TradeAction']

export const tradesApi = {
  list: (params?: {
    position_id?: string
    order_group_id?: string
    include_archived?: boolean
  }) => http.get(`/api/trades${buildQuery(params)}`) as Promise<Trade[]>,

  /** Single-row create. Backend always returns TradeRead[]. */
  create: (payload: TradeCreate) =>
    http.post('/api/trades', payload) as Promise<Trade[]>,

  /** Multi-leg create. Backend assigns one shared order_group_id across all rows. */
  createMany: (payloads: TradeCreate[]) =>
    http.post('/api/trades', payloads) as Promise<Trade[]>,

  update: (id: string, payload: TradeUpdate) =>
    http.patch(`/api/trades/${id}`, payload) as Promise<Trade>,

  /** Soft-delete (sets archived_at). */
  remove: (id: string) =>
    http.delete(`/api/trades/${id}`) as Promise<null>,
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${qs.toString()}`
}
