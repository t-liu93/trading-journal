<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
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
const executed_at = ref<number | null>(Date.now())
const notes = ref('')
type LegField = 'instrument' | 'action' | 'quantity' | 'price' | 'commission' | 'fees' | 'executed_at'
const fieldError = ref<Partial<Record<LegField, string>>>({})

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
watch(instrument_id, () => { delete fieldError.value.instrument })
watch(action, () => { delete fieldError.value.action })
watch(quantity, () => { delete fieldError.value.quantity })
watch(price, () => { delete fieldError.value.price })
watch(commission, () => { delete fieldError.value.commission })
watch(fees, () => { delete fieldError.value.fees })
watch(executed_at, () => { delete fieldError.value.executed_at })
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
  fieldError.value = {}
  if (executed_at.value == null || !Number.isFinite(executed_at.value)) fieldError.value.executed_at = 'Trade date and time is required'
  else if (!instrument_id.value) fieldError.value.instrument = 'Instrument is required'
  else if ((props.primaryInstrumentLoading || props.primaryInstrumentError) && selectedInstrument.value?.kind === 'option') fieldError.value.instrument = 'Resolve the primary instrument before selecting an option'
  else if (selectedInstrument.value?.kind === 'option' && primaryUnderlyingId.value && selectedInstrument.value.option?.underlying_id !== primaryUnderlyingId.value) fieldError.value.instrument = 'Option must match the primary instrument underlying'
  else if (!action.value) fieldError.value.action = 'Action is required'
  else if (quantity.value == null || quantity.value <= 0) fieldError.value.quantity = 'Quantity must be > 0'
  else if (price.value == null || price.value < 0) fieldError.value.price = 'Price must be >= 0'
  else if (commission.value != null && commission.value < 0) fieldError.value.commission = 'Commission must be >= 0'
  else if (fees.value != null && fees.value < 0) fieldError.value.fees = 'Fees must be >= 0'
  const key = (['executed_at', 'instrument', 'action', 'quantity', 'price', 'commission', 'fees'] as const).find(field => fieldError.value[field])
  return key ? fieldError.value[key]! : null
}

function showServerError(field: LegField, detail: string) {
  fieldError.value = { [field]: detail }
}

async function focusValidationError() {
  const key = (['executed_at', 'instrument', 'action', 'quantity', 'price', 'commission', 'fees'] as const).find(field => fieldError.value[field])
  if (!key) return
  await nextTick()
  const container = document.querySelector<HTMLElement>(`[data-leg-id="${rootId}"] [data-field="${key}"]`)
  if (!container) return
  container.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  const control = container.querySelector<HTMLElement>('input, [role="combobox"], button, textarea, [tabindex]:not([tabindex="-1"])')
  control?.focus()
}

const rootId = `leg-${Math.random().toString(36).slice(2)}`

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
    executed_at: executed_at.value == null ? '' : new Date(executed_at.value).toISOString(),
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

defineExpose({ validate, focusValidationError, showServerError, toPayload, reset, executed_at, instrument_id, notes })
</script>

<template>
  <n-card size="small" class="trade-leg" :data-leg-id="rootId">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
      <n-text strong>Leg</n-text>
      <n-button v-if="removable" size="tiny" type="error" quaternary @click="emit('remove')">Remove</n-button>
    </div>
    <div class="leg-fields">
      <div class="leg-field leg-field--wide" data-field="instrument">
        <div class="field-label">Instrument <span class="required">*</span></div>
          <InstrumentPicker
            v-model:model-value="instrument_id"
            :allow-create="true"
            :option-underlying-id="primaryUnderlyingId"
            :related-underlying-id="primaryUnderlyingId"
            :search-context-key="primaryInstrument?.id ?? null"
            :option-context-ready="!primaryInstrumentLoading && !primaryInstrumentError"
            :underlying-instrument="optionUnderlyingInstrument ?? (primaryInstrument?.kind === 'stock' ? primaryInstrument : null)"
            class="field-control"
            placeholder="Search instrument…"
            @update:instrument="handleInstrumentUpdate"
          />
          <n-tag v-if="selectedInstrument" size="small" type="info">{{ selectedInstrument.kind }}</n-tag>
        <n-text v-if="primaryInstrumentLoading" tag="div" depth="3" class="field-help">Loading the primary instrument. Option selection is paused.</n-text>
        <n-text v-else-if="primaryInstrumentError" tag="div" type="error" class="field-error" role="alert">{{ primaryInstrumentError }}</n-text>
        <n-text v-if="fieldError.instrument" tag="div" type="error" class="field-error" role="alert">{{ fieldError.instrument }}</n-text>
      </div>

      <div class="leg-field" data-field="action">
        <div class="field-label">Action <span class="required">*</span></div>
          <n-select
            v-model:value="action"
            :options="filteredActions"
            placeholder="Select action"
            class="field-control"
          />
        <n-text v-if="fieldError.action" tag="div" type="error" class="field-error" role="alert">{{ fieldError.action }}</n-text>
      </div>

      <div class="leg-field" data-field="quantity">
          <div class="field-label">Quantity <span class="required">*</span></div>
          <n-input-number
            v-model:value="quantity"
            placeholder="0"
            :min="0.001"
            :step="isOptionKind ? 1 : undefined"
            :precision="isOptionKind ? 0 : undefined"
            class="field-control"
          />
        <n-text v-if="fieldError.quantity" tag="div" type="error" class="field-error" role="alert">{{ fieldError.quantity }}</n-text>
      </div>

      <div class="leg-field" data-field="price">
          <div class="field-label">Price <span class="required">*</span></div>
          <n-input-number
            v-model:value="price"
            placeholder="0.00"
            :min="0"
            class="field-control"
          />
        <n-text v-if="fieldError.price" tag="div" type="error" class="field-error" role="alert">{{ fieldError.price }}</n-text>
      </div>

      <div class="leg-field" data-field="commission">
          <div class="field-label">Commission</div>
          <n-input-number
            v-model:value="commission"
            placeholder="0"
            :min="0"
            class="field-control"
          />
        <n-text v-if="fieldError.commission" tag="div" type="error" class="field-error" role="alert">{{ fieldError.commission }}</n-text>
      </div>

      <div class="leg-field" data-field="fees">
          <div class="field-label">Fees</div>
          <n-input-number
            v-model:value="fees"
            placeholder="0"
            :min="0"
            class="field-control"
          />
        <n-text v-if="fieldError.fees" tag="div" type="error" class="field-error" role="alert">{{ fieldError.fees }}</n-text>
      </div>

      <div class="leg-field" data-field="executed_at">
          <div class="field-label">Trade date and time <span class="required">*</span></div>
          <n-date-picker
            v-model:value="executed_at"
            type="datetime"
            clearable
            class="field-control"
          />
          <n-text v-if="fieldError.executed_at" tag="div" type="error" class="field-error" role="alert">{{ fieldError.executed_at }}</n-text>
          <n-text tag="div" depth="3" class="field-help">Used to place this trade in your history.</n-text>
      </div>

      <div class="leg-field leg-field--wide">
          <div class="field-label">Notes</div>
          <n-input
            v-model:value="notes"
            type="textarea"
            placeholder="Optional"
            :maxlength="4000"
            size="small"
            class="field-control"
          />
      </div>
    </div>

    <div v-if="cashFlowPreview !== null" style="margin-top: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
      <n-tag size="small" :type="cashFlowPreview >= 0 ? 'success' : 'error'" :bordered="false">
        Cash Flow Preview
      </n-tag>
      <span :style="{ color: cashFlowPreview >= 0 ? '#18a058' : '#d03050', fontWeight: 500 }">
        {{ currency ?? '' }} {{ new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cashFlowPreview) }}
      </span>
      <n-text tag="span" depth="3" class="field-help">Estimated cash received or paid for this trade after commission and fees.</n-text>
    </div>
  </n-card>
</template>

<style scoped>
.trade-leg { margin-bottom: 0.75rem; min-width: 0; }
.leg-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.75rem 1rem; min-width: 0; }
.leg-field { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
.leg-field--wide { grid-column: 1 / -1; }
.field-label { font-size: 0.875rem; font-weight: 500; }
.required { color: var(--n-color-error, #d03050); }
.field-control { width: 100%; min-width: 0; }
.field-help { font-size: 0.75rem; line-height: 1.35; }
.field-error { font-size: 0.8rem; line-height: 1.35; }
@media (max-width: 599px) { .leg-fields { grid-template-columns: minmax(0, 1fr); } .leg-field--wide { grid-column: auto; } }
</style>
