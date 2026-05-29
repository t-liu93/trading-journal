<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type FormInst, type FormRules, useMessage } from 'naive-ui'
import { type Position, type PositionCreate, type PositionUpdate, type StrategyType, positionsApi } from '../api/positions'
import { type Account, accountsApi } from '../api/accounts'
import { type Instrument, instrumentsApi } from '../api/instruments'
import { tradesApi } from '../api/trades'
import InstrumentPicker from './InstrumentPicker.vue'
import TradeEntryModal from './TradeEntryModal.vue'
import { ApiError } from '../api/types'

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
const tradeEntryRef = ref<InstanceType<typeof TradeEntryModal> | null>(null)
// Full Position object saved when Position POST succeeds but Trade POST fails.
// Allows retry without a second GET, and prevents duplicate Position creation.
const orphanPosition = ref<Position | null>(null)

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

const isOrphanRetry = computed(() => !!orphanPosition.value)

const createRules: FormRules = {
  account_id: [{ required: true, message: 'Account is required' }],
  primary_instrument_id: [{ required: true, message: 'Instrument is required' }],
  strategy_type: [{ required: true, message: 'Strategy is required' }],
}

watch(() => props.show, async (visible) => {
  if (!visible) return

  orphanPosition.value = null

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
      opened_at: null,
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
  // If orphan position exists, emit saved without a position so parent refreshes list
  if (orphanPosition.value) {
    orphanPosition.value = null
    emit('saved')
  }
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
      // Atomic Position+Trade flow (F4)
      const rows = tradeEntryRef.value?.getRows() ?? []
      if (rows.length === 0) {
        message.error('At least one Trade is required to create a Position.')
        submitting.value = false
        return
      }
      if (!tradeEntryRef.value?.validate()) {
        submitting.value = false
        return
      }

      // If we have an orphan from a previous failed attempt, reuse it
      let position: Position

      if (!orphanPosition.value) {
        // 1. derive opened_at from the earliest row's executed_at
        const opened_at = rows
          .map(r => r.executed_at)
          .sort()[0]

        // 2. create position
        const payload: PositionCreate = {
          account_id: model.value.account_id!,
          primary_instrument_id: model.value.primary_instrument_id!,
          strategy_type: model.value.strategy_type!,
          opened_at,
        }
        if (model.value.capital_used !== null) payload.capital_used = model.value.capital_used
        if (model.value.max_risk_at_open !== null) payload.max_risk_at_open = model.value.max_risk_at_open
        if (model.value.max_reward_at_open !== null) payload.max_reward_at_open = model.value.max_reward_at_open
        if (model.value.notes) payload.notes = model.value.notes

        position = await positionsApi.create(payload)
      } else {
        position = orphanPosition.value
      }

      // 3. create trade(s)
      const tradesPayload = rows.map(r => ({ ...r, position_id: position.id }))
      try {
        if (tradesPayload.length === 1) {
          await tradesApi.create(tradesPayload[0])
        } else {
          await tradesApi.createMany(tradesPayload)
        }
      } catch (e) {
        // Save full position object so retry can reuse it without a GET
        orphanPosition.value = position
        message.error(
          `Position created (id=${position.id}) but Trade(s) failed: ` +
          `${e instanceof ApiError ? e.message : 'unknown error'}. ` +
          `You can retry — trades will be posted to the same position.`,
        )
        submitting.value = false
        return
      }

      // Trade(s) created successfully — only NOW clear orphan state
      orphanPosition.value = null
      message.success('Position and Trade(s) created')
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
      <!-- Orphan retry banner -->
      <n-alert v-if="isOrphanRetry" type="warning" style="margin-bottom: 1rem;">
        Position was already created. Retry will only submit the Trade rows to the same position.
      </n-alert>
      <n-form-item label="Account" path="account_id">
        <n-select
          v-model:value="model.account_id"
          :options="accountOptions"
          placeholder="Select account"
          :disabled="mode === 'edit' || submitting || isOrphanRetry"
        />
      </n-form-item>

      <n-form-item label="Primary Instrument" path="primary_instrument_id">
        <div style="display: flex; align-items: center; gap: 0.5rem; width: 100%;">
          <InstrumentPicker
            :model-value="model.primary_instrument_id"
            :allow-create="mode === 'create'"
            :disabled="mode === 'edit' || submitting || isOrphanRetry"
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
          :disabled="mode === 'edit' || submitting || isOrphanRetry"
        />
      </n-form-item>

      <n-form-item v-if="mode === 'edit'" label="Opened At">
        <n-date-picker
          v-model:value="model.opened_at"
          type="datetime"
          style="width: 100%;"
          disabled
        />
        <n-text depth="3" style="font-size: 0.75rem; margin-left: 0.5rem;">
          Derived from first Trade executed_at
        </n-text>
      </n-form-item>

      <n-form-item label="Capital Used">
        <n-input-number
          v-model:value="model.capital_used"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting || isOrphanRetry"
        />
      </n-form-item>

      <n-form-item label="Max Risk at Open">
        <n-input-number
          v-model:value="model.max_risk_at_open"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting || isOrphanRetry"
        />
      </n-form-item>

      <n-form-item label="Max Reward at Open">
        <n-input-number
          v-model:value="model.max_reward_at_open"
          :placeholder="currencyLabel ? `${currencyLabel} amount` : 'Amount'"
          clearable
          style="width: 100%;"
          :disabled="submitting || isOrphanRetry"
        />
      </n-form-item>

      <n-form-item label="Notes">
        <n-input
          v-model:value="model.notes"
          type="textarea"
          :maxlength="4000"
          :disabled="submitting || isOrphanRetry"
          placeholder="Optional notes"
        />
      </n-form-item>

      <!-- First Trade inline form (create mode only) -->
      <template v-if="mode === 'create'">
        <n-divider />
        <n-h4 style="margin: 0 0 0.5rem;">First Trade</n-h4>
        <n-text depth="3" style="font-size: 0.85rem; display: block; margin-bottom: 0.5rem;">
          opened_at will be derived from the first Trade's executed_at.
        </n-text>
        <TradeEntryModal
          ref="tradeEntryRef"
          :inline="true"
          :account-id="model.account_id ?? ''"
          :currency="currencyLabel"
        />
      </template>
    </n-form>

    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
        <n-button
          type="primary"
          @click="handleSubmit"
          :loading="submitting"
        >
          {{ mode === 'create' ? 'Create' : 'Save' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>
