<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { usePmccMeta } from '../composables/usePmccMeta'
import InstrumentPicker from './InstrumentPicker.vue'
import { ApiError } from '../api/types'
import type { Instrument } from '../api/instruments'
import { getOptionUnderlyingId } from '../utils/instrumentContext'
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  positionId: string
  primaryInstrument?: Instrument | null
  primaryInstrumentLoading?: boolean
  primaryInstrumentError?: string | null
}>(), { primaryInstrument: null, primaryInstrumentLoading: false, primaryInstrumentError: null })
const emit = defineEmits<{ (e: 'retry-primary-instrument'): void }>()

const message = useMessage()
const { meta, loading, refresh, createOrUpdate, remove } = usePmccMeta(ref(props.positionId))

const leapInstrumentId = ref<string | null>(null)
const submitting = ref(false)
const compatiblePrimary = computed(() => props.primaryInstrument?.kind === 'stock')
const primaryUnderlyingId = computed(() => compatiblePrimary.value ? getOptionUnderlyingId(props.primaryInstrument) : null)

watch(meta, (val) => {
  if (val) {
    leapInstrumentId.value = val.leap_instrument_id
  }
})

onMounted(() => { void refresh() })

async function handleSubmit() {
  if (!compatiblePrimary.value || props.primaryInstrumentLoading || props.primaryInstrumentError) {
    message.warning('PMCC LEAP requires a resolved stock primary instrument.')
    return
  }
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
        <InstrumentPicker v-model:model-value="leapInstrumentId" kind="option" :allow-create="true"
          :underlying-instrument="compatiblePrimary ? primaryInstrument : null"
          :option-underlying-id="primaryUnderlyingId"
          :option-context-ready="compatiblePrimary && !primaryInstrumentLoading && !primaryInstrumentError"
          :disabled="!compatiblePrimary || primaryInstrumentLoading || Boolean(primaryInstrumentError)" />
      </n-form-item>
      <n-alert v-if="primaryInstrumentLoading" type="info" :bordered="false" style="margin-bottom: 0.75rem;">Loading the primary instrument…</n-alert>
      <n-alert v-else-if="primaryInstrumentError" type="error" :bordered="false" style="margin-bottom: 0.75rem;">
        {{ primaryInstrumentError }} <n-button size="tiny" @click="emit('retry-primary-instrument')">Retry</n-button>
      </n-alert>
      <n-text v-else-if="!compatiblePrimary" depth="3" style="font-size: 0.8rem; display: block; margin-bottom: 0.75rem;">
        PMCC LEAP metadata requires this Position's primary instrument to be a stock. Select a stock primary instrument to choose a matching LEAP.
      </n-text>
      <n-text v-else depth="3" style="font-size: 0.8rem; display: block; margin-bottom: 0.75rem;">
        Choose an option whose underlying is {{ primaryInstrument?.symbol }}. The server validates the saved association.
      </n-text>
    </n-form>

    <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem;">
      <n-popconfirm v-if="meta" @positive-click="handleDelete">
        <template #trigger>
          <n-button type="error" :disabled="submitting">Delete Meta</n-button>
        </template>
        Delete PMCC meta for this position?
      </n-popconfirm>
      <n-button type="primary" @click="handleSubmit" :loading="submitting" :disabled="!compatiblePrimary || primaryInstrumentLoading || Boolean(primaryInstrumentError)">
        {{ meta ? 'Save' : 'Create PMCC Meta' }}
      </n-button>
    </div>
  </n-spin>
</template>
