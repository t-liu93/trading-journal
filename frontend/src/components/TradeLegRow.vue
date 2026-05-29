<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type TradeAction, type TradeCreate } from '../api/trades'
import { type Instrument, instrumentsApi } from '../api/instruments'
import InstrumentPicker from './InstrumentPicker.vue'
import { previewCashFlow, isValidActionForKind } from '../utils/tradeCashFlow'

const props = defineProps<{
  accountId: string
  removable: boolean
  currency?: string
}>()

const emit = defineEmits<{
  (e: 'remove'): void
}>()

const instrument_id = ref<string | null>(null)
const selectedInstrument = ref<Instrument | null>(null)
const action = ref<TradeAction | null>(null)
const quantity = ref<number | null>(null)
const price = ref<number | null>(null)
const commission = ref<number | null>(null)
const fees = ref<number | null>(null)
const executed_at = ref<number>(Date.now())
const notes = ref('')

const TRADE_ACTIONS: { label: string; value: TradeAction }[] = [
  { label: 'BUY', value: 'buy' },
  { label: 'SELL', value: 'sell' },
  { label: 'BTO', value: 'bto' },
  { label: 'STO', value: 'sto' },
  { label: 'BTC', value: 'btc' },
  { label: 'STC', value: 'stc' },
]

const filteredActions = computed(() =>
  TRADE_ACTIONS.filter(opt => {
    if (!selectedInstrument.value) return true
    return isValidActionForKind(opt.value, selectedInstrument.value.kind)
  }),
)

const isOptionKind = computed(() => selectedInstrument.value?.kind === 'option')

const cashFlowPreview = computed(() => {
  if (!action.value || !instrument_id.value || quantity.value == null || price.value == null) return null
  return previewCashFlow(
    { action: action.value, price: price.value, quantity: quantity.value, commission: commission.value ?? 0, fees: fees.value ?? 0 },
    selectedInstrument.value ?? { kind: 'stock' },
  )
})

watch(instrument_id, async (id) => {
  if (id) {
    try {
      selectedInstrument.value = await instrumentsApi.get(id)
    } catch { selectedInstrument.value = null }
    if (action.value && selectedInstrument.value && !isValidActionForKind(action.value, selectedInstrument.value.kind)) {
      action.value = null
    }
  } else {
    selectedInstrument.value = null
  }
})

function validate(): string | null {
  if (!instrument_id.value) return 'Instrument is required'
  if (!action.value) return 'Action is required'
  if (quantity.value == null || quantity.value <= 0) return 'Quantity must be > 0'
  if (price.value == null || price.value < 0) return 'Price must be >= 0'
  return null
}

function toPayload(positionId?: string): TradeCreate {
  return {
    position_id: positionId ?? '',
    instrument_id: instrument_id.value!,
    action: action.value!,
    quantity: quantity.value!,
    price: price.value!,
    commission: commission.value ?? 0,
    fees: fees.value ?? 0,
    executed_at: new Date(executed_at.value).toISOString(),
    notes: notes.value || null,
  }
}

function reset() {
  instrument_id.value = null
  selectedInstrument.value = null
  action.value = null
  quantity.value = null
  price.value = null
  commission.value = null
  fees.value = null
  executed_at.value = Date.now()
  notes.value = ''
}

defineExpose({ validate, toPayload, reset, executed_at, instrument_id })
</script>

<template>
  <n-card size="small" style="margin-bottom: 0.75rem;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
      <n-text strong>Leg</n-text>
      <n-button v-if="removable" size="tiny" type="error" quaternary @click="emit('remove')">Remove</n-button>
    </div>
    <n-grid :cols="2" :x-gap="12" :y-gap="8">
      <n-grid-item span="2">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <n-text style="min-width: 70px; font-size: 0.85rem;">Instrument *</n-text>
          <InstrumentPicker
            v-model:model-value="instrument_id"
            :allow-create="true"
            style="flex: 1;"
            placeholder="Search instrument…"
          />
          <n-tag v-if="selectedInstrument" size="small" type="info">{{ selectedInstrument.kind }}</n-tag>
        </div>
      </n-grid-item>

      <n-grid-item span="2">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <n-text style="min-width: 70px; font-size: 0.85rem;">Action *</n-text>
          <n-select
            v-model:value="action"
            :options="filteredActions"
            placeholder="Select action"
            style="flex: 1;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="1">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Quantity *</n-text>
          <n-input-number
            v-model:value="quantity"
            placeholder="0"
            :min="0.001"
            :step="isOptionKind ? 1 : undefined"
            :precision="isOptionKind ? 0 : undefined"
            style="width: 100%;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="1">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Price *</n-text>
          <n-input-number
            v-model:value="price"
            placeholder="0.00"
            :min="0"
            style="width: 100%;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="1">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Commission</n-text>
          <n-input-number
            v-model:value="commission"
            placeholder="0"
            :min="0"
            style="width: 100%;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="1">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Fees</n-text>
          <n-input-number
            v-model:value="fees"
            placeholder="0"
            :min="0"
            style="width: 100%;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="2">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Executed At *</n-text>
          <n-date-picker
            v-model:value="executed_at"
            type="datetime"
            style="width: 100%;"
          />
        </div>
      </n-grid-item>

      <n-grid-item span="2">
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <n-text style="font-size: 0.85rem;">Notes</n-text>
          <n-input
            v-model:value="notes"
            type="textarea"
            placeholder="Optional"
            :maxlength="4000"
            size="small"
          />
        </div>
      </n-grid-item>
    </n-grid>

    <div v-if="cashFlowPreview !== null" style="margin-top: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
      <n-tag size="small" :type="cashFlowPreview >= 0 ? 'success' : 'error'" :bordered="false">
        Cash Flow Preview
      </n-tag>
      <span :style="{ color: cashFlowPreview >= 0 ? '#18a058' : '#d03050', fontWeight: 500 }">
        {{ currency ?? '' }} {{ new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cashFlowPreview) }}
      </span>
      <n-text depth="3" style="font-size: 0.75rem;">(server is source of truth)</n-text>
    </div>
  </n-card>
</template>
