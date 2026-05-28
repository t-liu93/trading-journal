import { ref } from 'vue'
import type { Ref } from 'vue'
import { type WheelMeta, type WheelMetaCreate, type WheelMetaUpdate, wheelMetaApi } from '../api/strategyMeta'
import { ApiError } from '../api/types'

export function useWheelMeta(positionId: Ref<string>) {
  const meta = ref<WheelMeta | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await wheelMetaApi.get(positionId.value)
      if (seq === refreshSeq) meta.value = result
    } catch (err) {
      if (seq === refreshSeq) {
        if (err instanceof ApiError && err.status === 404) {
          meta.value = null
        } else {
          error.value = err instanceof ApiError ? err.message : 'Failed to load wheel meta'
        }
      }
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function createOrUpdate(payload: WheelMetaCreate | WheelMetaUpdate): Promise<void> {
    if (meta.value === null) {
      await wheelMetaApi.create(positionId.value, payload as WheelMetaCreate)
    } else {
      await wheelMetaApi.update(positionId.value, payload as WheelMetaUpdate)
    }
    await refresh()
  }

  async function remove(): Promise<void> {
    await wheelMetaApi.remove(positionId.value)
    meta.value = null
  }

  return { meta, loading, error, refresh, createOrUpdate, remove }
}
