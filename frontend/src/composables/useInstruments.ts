import { ref, watch } from 'vue'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'
import { ApiError } from '../api/types'

const VALID_KINDS: InstrumentKind[] = ['stock', 'option', 'forex']

export function useInstruments() {
  const instruments = ref<Instrument[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** Empty string means "all kinds". */
  const kindFilter = ref('')
  const query = ref('')

  let refreshSeq = 0
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    const kind: InstrumentKind | undefined = VALID_KINDS.includes(kindFilter.value as InstrumentKind)
      ? (kindFilter.value as InstrumentKind)
      : undefined
    try {
      const result = await instrumentsApi.list({
        kind,
        q: query.value || undefined,
      })
      if (seq === refreshSeq) instruments.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        error.value = err instanceof ApiError ? err.message : 'Failed to load instruments.'
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  function debouncedRefresh() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => void refresh(), 300)
  }

  watch(kindFilter, () => void refresh())
  watch(query, () => debouncedRefresh())

  return { instruments, loading, error, kindFilter, query, refresh }
}
