import { ref } from 'vue'
import type { Ref } from 'vue'
import { type PmccMeta, type PmccMetaCreate, type PmccMetaUpdate, pmccMetaApi } from '../api/strategyMeta'
import { ApiError } from '../api/types'

export function usePmccMeta(positionId: Ref<string>) {
  const meta = ref<PmccMeta | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await pmccMetaApi.get(positionId.value)
      if (seq === refreshSeq) meta.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        if (err instanceof ApiError && err.status === 404) {
          meta.value = null
        } else {
          error.value = err instanceof ApiError ? err.message : 'Failed to load PMCC meta'
        }
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function createOrUpdate(payload: PmccMetaCreate | PmccMetaUpdate): Promise<void> {
    if (meta.value === null) {
      await pmccMetaApi.create(positionId.value, payload as PmccMetaCreate)
    } else {
      await pmccMetaApi.update(positionId.value, payload as PmccMetaUpdate)
    }
    await refresh()
  }

  async function remove(): Promise<void> {
    await pmccMetaApi.remove(positionId.value)
    meta.value = null
  }

  return { meta, loading, error, refresh, createOrUpdate, remove }
}
