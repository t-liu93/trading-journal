<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type TradeAction, type TradeCreate } from '../api/trades'
import { type Instrument, instrumentsApi } from '../api/instruments'
import { useMessage } from 'naive-ui'
import InstrumentPicker from './InstrumentPicker.vue'
import { previewCashFlow, isValidActionForKind } from '../utils/tradeCashFlow'
import { getOptionUnderlyingId } from '../utils/instrumentContext'

const props = defineProps<{
  accountId: string
  removable: boolean
  currency?: string
  primaryInstrument?: Instrument | null
  optionUnderlyingInstrument?: Instrument | null
  primaryInstrumentLoading?: boolean
  primaryInstrumentError?: string | null
}>()

const emit = defineEmits<{
  (e: 'remove'): void
}>()

const message = useMessage()
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

const primaryUnderlyingId = computed(() => getOptionUnderlyingId(props.primaryInstrument ?? null))
let instrumentRequest = 0
let previousUnderlyingId: string | null = primaryUnderlyingId.value

function clearIncompatibleOption(next: string | null) {
  instrument_id.value = null
  selectedInstrument.value = null
  message.warning(next
    ? 'The selected option was cleared because the primary underlying changed.'
    : props.primaryInstrument
      ? 'The selected option was cleared because the primary instrument has no compatible underlying.'
      : 'The selected option was cleared because the primary instrument was removed.')
}

async function resolveSelectedInstrument(id: string | null) {
  const seq = ++instrumentRequest
  if (!id) { selectedInstrument.value = null; return }
  if (selectedInstrument.value?.id !== id) selectedInstrument.value = null
  try {
    const instrument = await instrumentsApi.get(id)
    if (seq !== instrumentRequest || instrument_id.value !== id) return
    if (instrument.id !== id) return
    if (instrument.kind === 'option' && props.primaryInstrumentLoading) return
    if (instrument.kind === 'option' && primaryUnderlyingId.value && instrument.option?.underlying_id !== primaryUnderlyingId.value) {
      clearIncompatibleOption(primaryUnderlyingId.value)
      return
    }
    selectedInstrument.value = instrument
    if (action.value && !isValidActionForKind(action.value, instrument.kind)) action.value = null
  } catch {
    if (seq === instrumentRequest && selectedInstrument.value?.id !== id) selectedInstrument.value = null
  }
}

watch(instrument_id, id => { void resolveSelectedInstrument(id) })
watch([primaryUnderlyingId, () => props.primaryInstrumentLoading, () => props.primaryInstrumentError], async ([underlyingId, loading, error]) => {
  if (loading || error) {
    instrumentRequest += 1
    return
  }
  // Compare only resolved contexts. During stock -> forex/null resolution the
  // intermediate null is not authoritative and must not consume the old ID.
  const previous = previousUnderlyingId
  previousUnderlyingId = underlyingId
  const contextChanged = previous !== underlyingId
  const currentId = instrument_id.value
  if (!currentId || !contextChanged) return
  if (underlyingId === null) {
    await resolveSelectedInstrument(currentId)
    if (instrument_id.value === currentId && selectedInstrument.value?.kind === 'option') clearIncompatibleOption(null)
    return
  }
  await resolveSelectedInstrument(currentId)
  if (instrument_id.value === currentId && selectedInstrument.value?.kind === 'option'
    && (underlyingId === null || selectedInstrument.value.option?.underlying_id !== underlyingId)) {
    clearIncompatibleOption(underlyingId)
  }
})
watch(() => props.primaryInstrumentLoading, (loading) => {
  if (loading) {
    instrumentRequest += 1
  } else if (!props.primaryInstrumentError && instrument_id.value) {
    void resolveSelectedInstrument(instrument_id.value)
  }
})

function validate(): string | null {
  if (!instrument_id.value) return 'Instrument is required'
  if ((props.primaryInstrumentLoading || props.primaryInstrumentError) && selectedInstrument.value?.kind === 'option') return 'Resolve the primary instrument before selecting an option'
  if (selectedInstrument.value?.kind === 'option' && primaryUnderlyingId.value && selectedInstrument.value.option?.underlying_id !== primaryUnderlyingId.value) return 'Option must match the primary instrument underlying'
  if (!action.value) return 'Action is required'
  if (quantity.value == null || quantity.value <= 0) return 'Quantity must be > 0'
  if (price.value == null || price.value < 0) return 'Price must be >= 0'
  return null
}

function handleInstrumentUpdate(inst: Instrument | null) {
  const id = instrument_id.value
  instrumentRequest += 1
  if (!inst || inst.id !== id) { selectedInstrument.value = null; return }
  if (inst.kind === 'option' && (props.primaryInstrumentLoading || props.primaryInstrumentError || (primaryUnderlyingId.value && inst.option?.underlying_id !== primaryUnderlyingId.value))) {
    instrument_id.value = null
    selectedInstrument.value = null
    message.warning('Choose an option after the primary instrument context is ready, and only on its underlying.')
    return
  }
  selectedInstrument.value = inst
  if (action.value && !isValidActionForKind(action.value, inst.kind)) action.value = null
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

defineExpose({ validate, toPayload, reset, executed_at, instrument_id, notes })
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
            :option-underlying-id="primaryUnderlyingId"
            :option-context-ready="!primaryInstrumentLoading && !primaryInstrumentError"
            :underlying-instrument="optionUnderlyingInstrument ?? (primaryInstrument?.kind === 'stock' ? primaryInstrument : null)"
            style="flex: 1;"
            placeholder="Search instrument…"
            @update:instrument="handleInstrumentUpdate"
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
