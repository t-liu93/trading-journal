<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { usePmccMeta } from '../composables/usePmccMeta'
import InstrumentPicker from './InstrumentPicker.vue'
import { ApiError } from '../api/types'

const props = defineProps<{ positionId: string }>()

const message = useMessage()
const { meta, loading, refresh, createOrUpdate, remove } = usePmccMeta(ref(props.positionId))

const leapInstrumentId = ref<string | null>(null)
const submitting = ref(false)

watch(meta, (val) => {
  if (val) {
    leapInstrumentId.value = val.leap_instrument_id
  }
})

onMounted(() => { void refresh() })

async function handleSubmit() {
  if (!leapInstrumentId.value) {
    message.warning('Please select a LEAP instrument')
    return
  }
  submitting.value = true
  try {
    await createOrUpdate({ leap_instrument_id: leapInstrumentId.value })
    message.success(meta.value ? 'PMCC meta updated' : 'PMCC meta created')
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to save PMCC meta')
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  try {
    await remove()
    message.success('PMCC meta deleted')
    leapInstrumentId.value = null
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to delete PMCC meta')
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-form label-placement="top">
      <n-form-item label="LEAP Instrument">
        <InstrumentPicker v-model:model-value="leapInstrumentId" kind="option" />
      </n-form-item>
      <n-text depth="3" style="font-size: 0.8rem; display: block; margin-bottom: 0.75rem;">
        LEAP must be an option on the same underlying as this position's primary instrument. The backend enforces this — pickers don't filter for it in V1.
      </n-text>
    </n-form>

    <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem;">
      <n-popconfirm v-if="meta" @positive-click="handleDelete">
        <template #trigger>
          <n-button type="error" :disabled="submitting">Delete Meta</n-button>
        </template>
        Delete PMCC meta for this position?
      </n-popconfirm>
      <n-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ meta ? 'Save' : 'Create PMCC Meta' }}
      </n-button>
    </div>
  </n-spin>
</template>
