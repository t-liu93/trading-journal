<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useWheelMeta } from '../composables/useWheelMeta'
import { ApiError } from '../api/types'

const props = defineProps<{ positionId: string }>()

const message = useMessage()
const { meta, loading, refresh, createOrUpdate, remove } = useWheelMeta(ref(props.positionId))

const fundingSourceOptions = [
  { label: 'Cash', value: 'cash' },
  { label: 'Mixed', value: 'mixed' },
  { label: 'Margin', value: 'margin' },
]

const model = ref<{
  funding_source: 'cash' | 'mixed' | 'margin'
  loan_amount: number | null
  interest_rate_apr: number | null
  interest_accrued: number | null
}>({
  funding_source: 'cash',
  loan_amount: null,
  interest_rate_apr: null,
  interest_accrued: null,
})

const submitting = ref(false)

watch(meta, (val) => {
  if (val) {
    model.value = {
      funding_source: val.funding_source,
      loan_amount: val.loan_amount ? Number(val.loan_amount) : null,
      interest_rate_apr: val.interest_rate_apr ? Number(val.interest_rate_apr) : null,
      interest_accrued: val.interest_accrued ? Number(val.interest_accrued) : null,
    }
  }
})

onMounted(() => { void refresh() })

async function handleSubmit() {
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      funding_source: model.value.funding_source,
      loan_amount: model.value.loan_amount,
      interest_rate_apr: model.value.interest_rate_apr,
      interest_accrued: model.value.interest_accrued,
    }
    await createOrUpdate(payload)
    message.success(meta.value ? 'Wheel meta updated' : 'Wheel meta created')
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to save wheel meta')
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  try {
    await remove()
    message.success('Wheel meta deleted')
    model.value = { funding_source: 'cash', loan_amount: null, interest_rate_apr: null, interest_accrued: null }
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to delete wheel meta')
  }
}
</script>

<template>
  <n-spin :show="loading">
    <n-form ref="formRef" :model="model" label-placement="top">
      <n-form-item label="Funding Source">
        <n-select v-model:value="model.funding_source" :options="fundingSourceOptions" />
      </n-form-item>

      <n-form-item label="Loan Amount">
        <n-input-number v-model:value="model.loan_amount" clearable style="width: 100%;" />
      </n-form-item>

      <n-form-item label="Interest Rate APR (%)">
        <n-input-number v-model:value="model.interest_rate_apr" clearable style="width: 100%;" :precision="6" :step="0.1" />
      </n-form-item>

      <n-form-item label="Interest Accrued">
        <n-input-number v-model:value="model.interest_accrued" clearable style="width: 100%;" />
      </n-form-item>
    </n-form>

    <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem;">
      <n-popconfirm v-if="meta" @positive-click="handleDelete">
        <template #trigger>
          <n-button type="error" :disabled="submitting">Delete Meta</n-button>
        </template>
        Delete wheel meta for this position?
      </n-popconfirm>
      <n-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ meta ? 'Save' : 'Create Wheel Meta' }}
      </n-button>
    </div>
  </n-spin>
</template>
