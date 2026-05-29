import { ref, watch } from 'vue'
import { type Position, type PositionStatus, type StrategyType, positionsApi } from '../api/positions'
import { ApiError } from '../api/types'

interface UsePositionsOptions {
  /** Initial status filter. Empty string means "all". Default: 'open'. */
  status?: PositionStatus | ''
  /** Initial strategy type filter. Empty string means "all". Default: ''. */
  strategyType?: StrategyType | ''
}

export function usePositions(options?: UsePositionsOptions) {
  const positions = ref<Position[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const statusFilter = ref<PositionStatus | ''>(options?.status ?? 'open')
  const strategyTypeFilter = ref<StrategyType | ''>(options?.strategyType ?? '')
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const status = statusFilter.value || undefined
      const strategy_type = strategyTypeFilter.value || undefined
      const result = await positionsApi.list({ status, strategy_type })
      if (seq === refreshSeq) positions.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load positions'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  watch([statusFilter, strategyTypeFilter], () => { void refresh() })

  return { positions, loading, error, statusFilter, strategyTypeFilter, refresh }
}
