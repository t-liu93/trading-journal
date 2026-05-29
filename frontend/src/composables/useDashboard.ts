import { ref } from 'vue'
import { type DashboardSummary, dashboardApi } from '../api/dashboard'
import { ApiError } from '../api/types'

export function useDashboard() {
  const summary = ref<DashboardSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await dashboardApi.summary()
      if (seq === refreshSeq) summary.value = result
    } catch (e) {
      if (seq === refreshSeq)
        error.value = e instanceof ApiError ? e.message : 'Failed to load dashboard'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  return { summary, loading, error, refresh }
}
