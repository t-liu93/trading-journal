<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type FormInst, type FormRules, useMessage } from 'naive-ui'
import { useRoute } from 'vue-router'
import { type Position, type PositionCreate, type PositionUpdate, type StrategyType, positionsApi } from '../api/positions'
import { type Account, accountsApi } from '../api/accounts'
import { type Instrument, instrumentsApi } from '../api/instruments'
import InstrumentPicker from './InstrumentPicker.vue'
import PositionFirstTradePlaceholder from './PositionFirstTradePlaceholder.vue'
import { ApiError } from '../api/types'

const route = useRoute()
const isLegacy = computed(() => route.query.legacy === 'true')

const props = defineProps<{
  show: boolean
  mode: 'create' | 'edit'
  positionId?: string
  initial?: Position | null
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved', position?: Position): void
}>()

const message = useMessage()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)

const accounts = ref<Account[]>([])
const selectedInstrument = ref<Instrument | null>(null)

const model = ref<{
  account_id: string | null
  primary_instrument_id: string | null
  strategy_type: StrategyType | null
  opened_at: number | null
  capital_used: number | null
  max_risk_at_open: number | null
  max_reward_at_open: number | null
  notes: string
}>({
  account_id: null,
  primary_instrument_id: null,
  strategy_type: null,
  opened_at: null,
  capital_used: null,
  max_risk_at_open: null,
  max_reward_at_open: null,
  notes: '',
})

const strategyOptions = [
  { label: 'Wheel', value: 'wheel' },
  { label: 'Iron Condor', value: 'iron_condor' },
  { label: 'PMCC', value: 'pmcc' },
  { label: 'Spot Stock', value: 'spot_stock' },
  { label: 'Spot Forex', value: 'spot_forex' },
]

const accountOptions = computed(() =>
  accounts.value
    .filter((a) => !a.archived_at)
    .map((a) => ({ label: `${a.name} (${a.base_currency})`, value: a.id })),
)

const currencyLabel = computed(() => selectedInstrument.value?.currency ?? '')

const createRules: FormRules = {
  account_id: [{ required: true, message: 'Account is required' }],
  primary_instrument_id: [{ required: true, message: 'Instrument is required' }],
  strategy_type: [{ required: true, message: 'Strategy is required' }],
  opened_at: [{ required: true, message: 'Opened at is required', type: 'number' }],
}

watch(() => props.show, async (visible) => {
  if (!visible) return

  if (props.mode === 'edit' && props.initial) {
    model.value = {
      account_id: props.initial.account_id,
      primary_instrument_id: props.initial.primary_instrument_id,
      strategy_type: props.initial.strategy_type,
      opened_at: new Date(props.initial.opened_at).getTime(),
      capital_used: props.initial.capital_used !== null ? Number(props.initial.capital_used) : null,
      max_risk_at_open: props.initial.max_risk_at_open !== null ? Number(props.initial.max_risk_at_open) : null,
      max_reward_at_open: props.initial.max_reward_at_open !== null ? Number(props.initial.max_reward_at_open) : null,
      notes: props.initial.notes ?? '',
    }
    try {
      selectedInstrument.value = await instrumentsApi.get(props.initial.primary_instrument_id)
    } catch { /* ignore */ }
  } else {
    model.value = {
      account_id: null,
      primary_instrument_id: null,
      strategy_type: null,
      opened_at: Date.now(),
      capital_used: null,
      max_risk_at_open: null,
      max_reward_at_open: null,
      notes: '',
    }
    selectedInstrument.value = null
  }

  try {
    accounts.value = await accountsApi.list()
  } catch { /* ignore */ }
})

async function handleInstrumentSelect(id: string | null) {
  model.value.primary_instrument_id = id
  if (id) {
    try {
      selectedInstrument.value = await instrumentsApi.get(id)
    } catch { selectedInstrument.value = null }
  } else {
    selectedInstrument.value = null
  }
}

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
    if (props.mode === 'create') {
      const payload: PositionCreate = {
        account_id: model.value.account_id!,
        primary_instrument_id: model.value.primary_instrument_id!,
        strategy_type: model.value.strategy_type!,
        opened_at: new Date(model.value.opened_at!).toISOString(),
      }
      if (model.value.capital_used !== null) payload.capital_used = model.value.capital_used
      if (model.value.max_risk_at_open !== null) payload.max_risk_at_open = model.value.max_risk_at_open
      if (model.value.max_reward_at_open !== null) payload.max_reward_at_open = model.value.max_reward_at_open
      if (model.value.notes) payload.notes = model.value.notes

      const position = await positionsApi.create(payload)
      message.success('Position created — attach first Trade via Trades tab (F4)')
      emit('saved', position)
    } else {
      const payload: PositionUpdate = {}
      if (model.value.capital_used !== null) payload.capital_used = model.value.capital_used
      else payload.capital_used = null
      if (model.value.max_risk_at_open !== null) payload.max_risk_at_open = model.value.max_risk_at_open
      else payload.max_risk_at_open = null
      if (model.value.max_reward_at_open !== null) payload.max_reward_at_open = model.value.max_reward_at_open
      else payload.max_reward_at_open = null
      payload.notes = model.value.notes || null

      await positionsApi.update(props.positionId!, payload)
      message.success('Position updated')
      emit('saved')
    }
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
    :title="mode === 'create' ? 'New Position' : 'Edit Position'"
    preset="card"
    style="max-width: 600px;"
    :mask-closable="!submitting"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="model" :rules="createRules" label-placement="top">
      <n-form-item label="Account" path="account_id">
        <n-select
          v-model:value="model.account_id"
          :options="accountOptions"
          placeholder="Select account"
          :disabled="mode === 'edit' || submitting"
        />
      </n-form-item>

      <n-form-item label="Primary Instrument" path="primary_instrument_id">
        <div style="display: flex; align-items: center; gap: 0.5rem; width: 100%;">
          <InstrumentPicker
            :model-value="model.primary_instrument_id"
            :allow-create="mode === 'create'"
            :disabled="mode === 'edit' || submitting"
            style="flex: 1;"
            @update:model-value="handleInstrumentSelect"
          />
          <n-tag v-if="currencyLabel" size="small" type="info">{{ currencyLabel }}</n-tag>
        </div>
      </n-form-item>

      <n-form-item label="Strategy" path="strategy_type">
        <n-select
          v-model:value="model.strategy_type"
          :options="strategyOptions"
          placeholder="Select strategy"
          :disabled="mode === 'edit' || submitting"
        />
      </n-form-item>

      <n-form-item label="Opened At" path="opened_at">
        <n-date-picker
          v-model:value="model.opened_at"
          type="datetime"
          style="width: 100%;"
          :disabled="mode === 'edit' || submitting"
        />
      </n-form-item>

      <n-form-item label="Capital Used">
        <n-input-number
          v-model:value="model.capital_used"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting"
        />
      </n-form-item>

      <n-form-item label="Max Risk at Open">
        <n-input-number
          v-model:value="model.max_risk_at_open"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting"
        />
      </n-form-item>

      <n-form-item label="Max Reward at Open">
        <n-input-number
          v-model:value="model.max_reward_at_open"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting"
        />
      </n-form-item>

      <n-form-item label="Notes">
        <n-input
          v-model:value="model.notes"
          type="textarea"
          :maxlength="4000"
          :disabled="submitting"
          placeholder="Optional notes"
        />
      </n-form-item>

      <template v-if="mode === 'create'">
        <n-divider />
        <n-h4 style="margin: 0 0 0.5rem;">First Trade</n-h4>
        <slot name="first-trade">
          <PositionFirstTradePlaceholder />
        </slot>
      </template>
    </n-form>

    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
        <n-button
          type="primary"
          @click="handleSubmit"
          :loading="submitting"
          :disabled="mode === 'create' && !isLegacy"
        >
          {{ mode === 'create' ? 'Create' : 'Save' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>
