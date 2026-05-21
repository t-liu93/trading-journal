<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type FormInst, type FormRules, useMessage } from 'naive-ui'
import { accountsApi, type Account, type AccountCreate, type AccountUpdate } from '../api/accounts'
import { ApiError } from '../api/types'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'edit'
  initial?: Account
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved', account: Account): void
}>()

const message = useMessage()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)

const title = computed(() => (props.mode === 'create' ? 'New Account' : 'Edit Account'))

const accountTypeOptions = [
  { label: 'Cash', value: 'cash' },
  { label: 'Margin', value: 'margin' },
  { label: 'Paper', value: 'paper' },
]

const currencyOptions = [
  { label: 'USD', value: 'USD' },
  { label: 'EUR', value: 'EUR' },
  { label: 'GBP', value: 'GBP' },
  { label: 'JPY', value: 'JPY' },
  { label: 'CHF', value: 'CHF' },
  { label: 'CAD', value: 'CAD' },
  { label: 'AUD', value: 'AUD' },
  { label: 'HKD', value: 'HKD' },
]

interface FormModel {
  name: string
  broker: string
  account_type: string | null
  base_currency: string | null
  notes: string
}

const model = ref<FormModel>({
  name: '',
  broker: '',
  account_type: null,
  base_currency: null,
  notes: '',
})

const rules: FormRules = {
  name: [
    { required: true, message: 'Name is required' },
    { max: 255, message: 'Max 255 characters' },
  ],
  broker: [
    { required: true, message: 'Broker is required' },
    { max: 255, message: 'Max 255 characters' },
  ],
  account_type: [
    { required: true, message: 'Account type is required' },
  ],
  base_currency: [
    { required: true, message: 'Currency is required' },
    {
      validator: (_rule, value) => {
        if (value && !/^[A-Z]{3}$/.test(value)) {
          return new Error('Must be a 3-letter currency code (e.g. USD)')
        }
        return true
      },
    },
  ],
}

function resetModel() {
  model.value = {
    name: '',
    broker: '',
    account_type: null,
    base_currency: null,
    notes: '',
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    if (props.mode === 'edit' && props.initial) {
      model.value = {
        name: props.initial.name,
        broker: props.initial.broker,
        account_type: props.initial.account_type,
        base_currency: props.initial.base_currency,
        notes: props.initial.notes ?? '',
      }
    } else {
      resetModel()
    }
  },
)

function handleClose() {
  emit('update:show', false)
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    let result: Account
    if (props.mode === 'create') {
      const payload: AccountCreate = {
        name: model.value.name,
        broker: model.value.broker,
        account_type: model.value.account_type as AccountCreate['account_type'],
        base_currency: model.value.base_currency!,
      }
      if (model.value.notes) payload.notes = model.value.notes
      result = await accountsApi.create(payload)
    } else {
      const payload: AccountUpdate = {}
      if (model.value.name !== (props.initial?.name ?? ''))
        payload.name = model.value.name
      if (model.value.broker !== (props.initial?.broker ?? ''))
        payload.broker = model.value.broker
      if (model.value.account_type !== (props.initial?.account_type ?? ''))
        payload.account_type = model.value.account_type as AccountUpdate['account_type']
      if (model.value.base_currency !== (props.initial?.base_currency ?? ''))
        payload.base_currency = model.value.base_currency
      const oldNotes = props.initial?.notes ?? ''
      if (model.value.notes !== oldNotes) payload.notes = model.value.notes || null
      result = await accountsApi.update(props.initial!.id, payload)
    }
    message.success(
      props.mode === 'create' ? `Account "${result.name}" created` : `Account "${result.name}" updated`,
    )
    emit('saved', result)
    handleClose()
  } catch (err) {
    if (err instanceof ApiError) {
      message.error(err.message)
    } else {
      throw err
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    :title="title"
    preset="card"
    style="max-width: 520px;"
    :mask-closable="!submitting"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="model" :rules="rules" label-placement="top">
      <n-form-item label="Name" path="name">
        <n-input v-model:value="model.name" placeholder="e.g. IBKR Margin" :disabled="submitting" />
      </n-form-item>

      <n-form-item label="Broker" path="broker">
        <n-input v-model:value="model.broker" placeholder="e.g. Interactive Brokers" :disabled="submitting" />
      </n-form-item>

      <n-form-item label="Account Type" path="account_type">
        <n-select
          v-model:value="model.account_type"
          :options="accountTypeOptions"
          placeholder="Select type"
          :disabled="submitting"
        />
      </n-form-item>

      <n-form-item label="Base Currency" path="base_currency">
        <n-select
          v-model:value="model.base_currency"
          :options="currencyOptions"
          placeholder="Select or type currency code"
          filterable
          tag
          :disabled="submitting"
        />
      </n-form-item>

      <n-form-item label="Notes" path="notes">
        <n-input
          v-model:value="model.notes"
          type="textarea"
          placeholder="Optional notes about this account"
          :disabled="submitting"
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
        <n-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ mode === 'create' ? 'Create' : 'Save' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>
