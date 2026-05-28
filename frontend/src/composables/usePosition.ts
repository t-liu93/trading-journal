import { ref } from 'vue'
import type { Ref } from 'vue'
import { type Position, type PositionUpdate, positionsApi } from '../api/positions'
import { ApiError } from '../api/types'
import { http } from '../api/http'

export interface Trade {
  id: string
  position_id: string
  account_id: string
  instrument_id: string
  action: string
  quantity: string
  price: string
  commission: string
  fees: string
  cash_flow: string
  executed_at: string
  order_group_id: string | null
  broker_trade_id: string | null
  notes: string | null
  archived_at: string | null
}

export function usePosition(positionId: Ref<string>) {
  const position = ref<Position | null>(null)
  const trades = ref<Trade[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const [pos, tradeList] = await Promise.all([
        positionsApi.get(positionId.value),
        http.get(`/api/trades?position_id=${positionId.value}`) as Promise<Trade[]>,
      ])
      if (seq === refreshSeq) {
        position.value = pos
        trades.value = tradeList
      }
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load position'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function update(payload: PositionUpdate): Promise<void> {
    await positionsApi.update(positionId.value, payload)
    await refresh()
  }

  async function close(): Promise<void> {
    await positionsApi.update(positionId.value, {
      status: 'closed',
      closed_at: new Date().toISOString(),
    })
    await refresh()
  }

  async function remove(): Promise<void> {
    await positionsApi.remove(positionId.value)
  }

  return { position, trades, loading, error, refresh, update, close, remove }
}
