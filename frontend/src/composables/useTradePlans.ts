import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { type TradePlan, type TradePlanCreate, tradePlansApi } from '../api/tradePlans'
import { ApiError } from '../api/types'

export function useTradePlans(positionId: Ref<string>) {
  const revisions = ref<TradePlan[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const current = computed(() => revisions.value[revisions.value.length - 1] ?? null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await tradePlansApi.list(positionId.value)
      if (seq === refreshSeq) revisions.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load trade plans'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function append(payload: TradePlanCreate): Promise<void> {
    await tradePlansApi.append(positionId.value, payload)
    await refresh()
  }

  return { revisions, current, loading, error, refresh, append }
}
