<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { tradePlansApi } from '../api/tradePlans'
import { ApiError } from '../api/types'

const props = defineProps<{ positionId: string; startExpanded?: boolean }>()
const emit = defineEmits<{ (e: 'saved'): void }>()

const message = useMessage()
const expanded = ref(props.startExpanded ?? false)
const submitting = ref(false)

const model = ref<{
  effective_at: number
  planned_entry: number | null
  planned_stop_loss: number | null
  planned_take_profit: number | null
  target_rr: number | null
  thesis: string
}>({
  effective_at: Date.now(),
  planned_entry: null,
  planned_stop_loss: null,
  planned_take_profit: null,
  target_rr: null,
  thesis: '',
})

function resetForm() {
  model.value = {
    effective_at: Date.now(),
    planned_entry: null,
    planned_stop_loss: null,
    planned_take_profit: null,
    target_rr: null,
    thesis: '',
  }
  if (!props.startExpanded) {
    expanded.value = false
  }
}

async function handleSubmit() {
  submitting.value = true
  try {
    await tradePlansApi.append(props.positionId, {
      effective_at: new Date(model.value.effective_at).toISOString(),
      planned_entry: model.value.planned_entry ?? undefined,
      planned_stop_loss: model.value.planned_stop_loss ?? undefined,
      planned_take_profit: model.value.planned_take_profit ?? undefined,
      target_rr: model.value.target_rr ?? undefined,
      thesis: model.value.thesis || undefined,
    })
    message.success('Revision appended')
    resetForm()
    emit('saved')
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to append revision')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div>
    <n-button v-if="!expanded" type="primary" ghost @click="expanded = true">
      + Append Revision
    </n-button>

    <template v-if="expanded">
      <n-divider style="margin: 0.75rem 0;" />
      <n-form ref="formRef" :model="model" label-placement="top">
        <n-form-item label="Effective At">
          <n-date-picker v-model:value="model.effective_at" type="datetime" style="width: 100%;" />
        </n-form-item>

        <n-form-item label="Planned Entry">
          <n-input-number v-model:value="model.planned_entry" clearable style="width: 100%;" />
        </n-form-item>

        <n-form-item label="Planned Stop Loss">
          <n-input-number v-model:value="model.planned_stop_loss" clearable style="width: 100%;" />
        </n-form-item>

        <n-form-item label="Planned Take Profit">
          <n-input-number v-model:value="model.planned_take_profit" clearable style="width: 100%;" />
        </n-form-item>

        <n-form-item label="Target R:R">
          <n-input-number v-model:value="model.target_rr" clearable style="width: 100%;" :precision="4" :step="0.1" />
        </n-form-item>

        <n-form-item label="Thesis">
          <n-input v-model:value="model.thesis" type="textarea" :maxlength="8000" placeholder="Why this trade plan?" />
        </n-form-item>
      </n-form>

      <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.75rem;">
        <n-button @click="resetForm">Cancel</n-button>
        <n-button type="primary" @click="handleSubmit" :loading="submitting">Submit</n-button>
      </div>
    </template>
  </div>
</template>
