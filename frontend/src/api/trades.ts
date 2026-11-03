import type { components } from './schema'
import { http } from './http'
import { utcTimestamp } from './datetimes'

export type Trade        = components['schemas']['TradeRead']
export type TradeCreate  = components['schemas']['TradeCreate']
export type TradeUpdate  = components['schemas']['TradeUpdate']
export type TradeAction  = components['schemas']['TradeAction']

function readTrade(value: unknown): Trade {
  const trade = value as Trade
  return { ...trade, executed_at: utcTimestamp(trade.executed_at) }
}
function readTrades(value: unknown): Trade[] {
  return (value as Trade[]).map(readTrade)
}

export const tradesApi = {
  list: (params?: {
    position_id?: string
    order_group_id?: string
    include_archived?: boolean
  }) => http.get(`/api/trades${buildQuery(params)}`).then(readTrades),

  /** Single-row create. Backend always returns TradeRead[]. */
  create: (payload: TradeCreate) =>
    http.post('/api/trades', payload).then(readTrades),

  /** Multi-leg create. Backend assigns one shared order_group_id across all rows. */
  createMany: (payloads: TradeCreate[]) =>
    http.post('/api/trades', payloads).then(readTrades),

  update: (id: string, payload: TradeUpdate) =>
    http.patch(`/api/trades/${id}`, payload).then(readTrade),

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
