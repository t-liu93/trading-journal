import { ref, watch } from 'vue'
import { type Trade, type TradeCreate, tradesApi } from '../api/trades'
import { ApiError } from '../api/types'

export function useTrades(positionId: string) {
  const trades = ref<Trade[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const includeArchived = ref(false)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await tradesApi.list({
        position_id: positionId,
        include_archived: includeArchived.value,
      })
      if (seq === refreshSeq) trades.value = result
    } catch (e) {
      if (seq === refreshSeq)
        error.value = e instanceof ApiError ? e.message : 'Failed to load trades'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function createMany(rows: TradeCreate[]): Promise<Trade[]> {
    const created = rows.length === 1
      ? await tradesApi.create(rows[0])
      : await tradesApi.createMany(rows)
    await refresh()
    return created
  }

  async function archive(id: string): Promise<void> {
    await tradesApi.remove(id)
    await refresh()
  }

  async function updateNotes(id: string, notes: string | null): Promise<void> {
    await tradesApi.update(id, { notes })
    await refresh()
  }

  watch(includeArchived, () => { void refresh() })

  return { trades, loading, error, includeArchived, refresh, createMany, archive, updateNotes }
}
