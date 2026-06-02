import { ref } from 'vue'
import type { Ref } from 'vue'
import { type Position, type PositionUpdate, positionsApi } from '../api/positions'
import { type Trade, tradesApi } from '../api/trades'
import { ApiError } from '../api/types'

export type { Trade }

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
        tradesApi.list({ position_id: positionId.value }),
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
    // closed_at is intentionally omitted: the backend derives it from the
    // last fill (MAX trade executed_at) so days_held reflects the actual
    // holding period rather than the moment "Close" was clicked.
    await positionsApi.update(positionId.value, {
      status: 'closed',
    })
    await refresh()
  }

  async function remove(): Promise<void> {
    await positionsApi.remove(positionId.value)
  }

  return { position, trades, loading, error, refresh, update, close, remove }
}
