import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'
import { ApiError } from '../api/types'

const VALID_KINDS: InstrumentKind[] = ['stock', 'option', 'forex']
const PAGE_SIZE = 50

export function useInstruments() {
  const instruments = ref<Instrument[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const kindFilter = ref('')
  const query = ref('')
  const includeExpired = ref(false)
  const offset = ref(0)
  const hasNext = ref(false)
  const hasPrevious = computed(() => offset.value > 0)

  let refreshSeq = 0
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function invalidate(clear = true) {
    refreshSeq += 1
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = null
    loading.value = false
    error.value = null
    hasNext.value = false
    if (clear) instruments.value = []
  }

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = null
    loading.value = true
    error.value = null
    const kind: InstrumentKind | undefined = VALID_KINDS.includes(kindFilter.value as InstrumentKind)
      ? (kindFilter.value as InstrumentKind)
      : undefined
    try {
      const result = await instrumentsApi.list({
        kind, q: query.value || undefined, limit: PAGE_SIZE + 1, offset: offset.value,
        include_expired: includeExpired.value,
      })
      if (seq === refreshSeq && !disposed) {
        hasNext.value = result.length > PAGE_SIZE
        instruments.value = result.slice(0, PAGE_SIZE)
      }
    } catch (err) {
      if (seq === refreshSeq && !disposed) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load instruments.'
        hasNext.value = false
      }
    } finally {
      if (seq === refreshSeq && !disposed) loading.value = false
    }
  }

  function scheduleRefresh() {
    invalidate()
    offset.value = 0
    const seq = refreshSeq
    debounceTimer = setTimeout(() => {
      if (seq === refreshSeq && !disposed) void refresh()
    }, 300)
  }

  function nextPage() {
    if (!hasNext.value || loading.value) return
    offset.value += PAGE_SIZE
    instruments.value = []
    void refresh()
  }

  function previousPage() {
    if (!hasPrevious.value || loading.value) return
    offset.value = Math.max(0, offset.value - PAGE_SIZE)
    instruments.value = []
    void refresh()
  }

  watch(kindFilter, scheduleRefresh, { flush: 'sync' })
  watch(query, scheduleRefresh, { flush: 'sync' })
  watch(includeExpired, scheduleRefresh, { flush: 'sync' })
  onBeforeUnmount(() => {
    disposed = true
    invalidate()
  })

  return {
    instruments, loading, error, kindFilter, query, includeExpired,
    offset, hasNext, hasPrevious, refresh, nextPage, previousPage,
  }
}
