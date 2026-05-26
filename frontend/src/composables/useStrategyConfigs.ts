import { ref } from 'vue'
import {
  type StrategyConfig,
  type StrategyConfigCreate,
  strategyConfigsApi,
} from '../api/strategyConfigs'
import { ApiError } from '../api/types'

export function useStrategyConfigs() {
  const configs = ref<StrategyConfig[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await strategyConfigsApi.list()
      if (seq === refreshSeq) configs.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load strategy configs.'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function upsert(payload: StrategyConfigCreate): Promise<StrategyConfig | null> {
    try {
      const result = await strategyConfigsApi.upsert(payload)
      await refresh()
      return result
    } catch (err) {
      throw err instanceof ApiError ? err : new Error('Failed to save strategy config.')
    }
  }

  return { configs, loading, error, refresh, upsert }
}
