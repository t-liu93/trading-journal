/**
 * Page-local Accounts state + actions.
 *
 * Composable instead of a Pinia store: each consuming view (Dashboard for the
 * count card, AccountsView for the full list) gets its own reactive copy.
 * Promote to a store only when ≥2 components need to react to the same
 * underlying state (cross-view sync); see frontend-implementation-plan-f1 §2.
 */

import { ref, watch } from 'vue'
import { type Account, accountsApi } from '../api/accounts'
import { ApiError } from '../api/types'

export function useAccounts() {
  const accounts = ref<Account[]>([])
  const loading = ref(false)
  /** Normalised, human-facing error message; null when last refresh succeeded. */
  const error = ref<string | null>(null)
  const includeArchived = ref(false)

  // Monotonic id so only the most recent refresh writes to state. Without this,
  // rapid "Show archived" toggling can let an older response overwrite a newer
  // one (last-resolved-wins instead of last-requested-wins).
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await accountsApi.list(includeArchived.value)
      if (seq === refreshSeq) accounts.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load accounts.'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  // Auto-refresh when the toggle flips. `immediate: false` so the first fetch
  // is explicit (done by the view's onMounted) — avoids a double-fetch on
  // initial render.
  watch(includeArchived, () => {
    void refresh()
  })

  return { accounts, loading, error, includeArchived, refresh }
}
