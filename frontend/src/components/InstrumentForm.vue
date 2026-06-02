<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { type FormInst, type FormRules, useMessage } from 'naive-ui'
import {
  instrumentsApi,
  type Instrument,
  type InstrumentKind,
  type StockCreate,
  type OptionCreate,
  type ForexCreate,
} from '../api/instruments'
import CurrencySelect from './CurrencySelect.vue'
import InstrumentPicker from './InstrumentPicker.vue'
import { ApiError } from '../api/types'

const props = defineProps<{
  show: boolean
  initialKind?: InstrumentKind
  initialSymbol?: string
  lockedKind?: InstrumentKind
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved', instrument: Instrument): void
}>()

const message = useMessage()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)

type KindKey = InstrumentKind
const kindTabs: { label: string; value: KindKey }[] = [
  { label: 'Stock', value: 'stock' },
  { label: 'Option', value: 'option' },
  { label: 'Forex', value: 'forex' },
]
const activeKind = ref<KindKey>('stock')
const lockedKind = computed<KindKey | null>(() => props.lockedKind ?? null)

const optTypeOptions = [
  { label: 'Call', value: 'call' },
  { label: 'Put', value: 'put' },
]
const styleOptions = [
  { label: 'American', value: 'american' },
  { label: 'European', value: 'european' },
]

interface StockModel {
  symbol: string
  exchange: string
  currency: string | null
}
interface OptionModel {
  // The chosen underlying stock instrument; symbol/currency/exchange below are
  // derived from it (an option must bind to an existing stock).
  underlying_instrument_id: string | null
  underlying_symbol: string
  underlying_exchange: string
  currency: string | null
  opt_type: 'call' | 'put' | null
  strike: string
  expiry: number | null
  multiplier: number
  style: 'american' | 'european'
}
interface ForexModel {
  symbol: string
  base_currency: string | null
  quote_currency: string | null
  pip_size: string
  contract_size: string
}

const stockModel = ref<StockModel>({ symbol: '', exchange: '', currency: null })
const optionModel = ref<OptionModel>({
  underlying_instrument_id: null,
  underlying_symbol: '',
  underlying_exchange: '',
  currency: null,
  opt_type: null,
  strike: '',
  expiry: null,
  multiplier: 100,
  style: 'american',
})
const forexModel = ref<ForexModel>({
  symbol: '',
  base_currency: null,
  quote_currency: null,
  pip_size: '',
  contract_size: '',
})

const currencyValidator = (_rule: unknown, value: string | null) => {
  if (!value) return new Error('Currency is required')
  if (!/^[A-Z]{3}$/.test(value)) return new Error('Must be a 3-letter currency code (e.g. USD)')
  return true
}
const positiveDecimalValidator = (field: string) => (_rule: unknown, value: string) => {
  if (!value) return new Error(`${field} is required`)
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return new Error(`${field} must be greater than 0`)
  return true
}
const optionalPositiveValidator = (field: string) => (_rule: unknown, value: string) => {
  if (!value) return true
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return new Error(`${field} must be greater than 0 if provided`)
  return true
}

const stockRules: FormRules = {
  symbol: [
    { required: true, message: 'Symbol is required' },
    { max: 64, message: 'Max 64 characters' },
  ],
  currency: [{ required: true, validator: currencyValidator }],
}
const optionRules: FormRules = {
  underlying_instrument_id: [
    { required: true, message: 'Select an underlying stock', trigger: ['change', 'blur'] },
  ],
  opt_type: [{ required: true, message: 'Option type is required' }],
  strike: [{ required: true, validator: positiveDecimalValidator('Strike') }],
  expiry: [{ required: true, message: 'Expiry date is required', type: 'number' }],
  multiplier: [{ required: true, message: 'Multiplier is required', type: 'number' }],
}
const forexRules: FormRules = {
  symbol: [
    { required: true, message: 'Symbol is required' },
    { max: 64, message: 'Max 64 characters' },
  ],
  base_currency: [{ required: true, validator: currencyValidator }],
  quote_currency: [{ required: true, validator: currencyValidator }],
  pip_size: [{ required: true, validator: positiveDecimalValidator('Pip size') }],
  contract_size: [{ validator: optionalPositiveValidator('Contract size') }],
}

const currentRules = computed(() => {
  if (activeKind.value === 'option') return optionRules
  if (activeKind.value === 'forex') return forexRules
  return stockRules
})
const currentModel = computed(() => {
  if (activeKind.value === 'option') return optionModel.value
  if (activeKind.value === 'forex') return forexModel.value
  return stockModel.value
})

function resetModels() {
  stockModel.value = { symbol: '', exchange: '', currency: null }
  optionModel.value = {
    underlying_instrument_id: null,
    underlying_symbol: '',
    underlying_exchange: '',
    currency: null,
    opt_type: null,
    strike: '',
    expiry: null,
    multiplier: 100,
    style: 'american',
  }
  forexModel.value = {
    symbol: '',
    base_currency: null,
    quote_currency: null,
    pip_size: '',
    contract_size: '',
  }
}

watch(() => props.show, (visible) => {
  if (visible) {
    resetModels()
    activeKind.value = lockedKind.value ?? props.initialKind ?? 'stock'
    if (props.initialSymbol) {
      // Options bind to an existing stock chosen via the picker, so a free-text
      // symbol hint only applies to the stock/forex tabs.
      const sym = props.initialSymbol
      if (activeKind.value === 'stock') stockModel.value.symbol = sym
      else if (activeKind.value === 'forex') forexModel.value.symbol = sym
    }
  }
})

watch(activeKind, (kind) => {
  if (lockedKind.value && kind !== lockedKind.value) {
    activeKind.value = lockedKind.value
  }
})

// Forex symbol auto-split: 6-letter symbol → base_currency + quote_currency.
// Opportunistic (only fills, never clears); both fields remain editable.
watch(() => forexModel.value.symbol, (s) => {
  if (s && /^[A-Za-z]{6}$/.test(s)) {
    forexModel.value.base_currency = s.slice(0, 3).toUpperCase()
    forexModel.value.quote_currency = s.slice(3, 6).toUpperCase()
  }
})

// Derive the option's underlying symbol/currency/exchange from the chosen stock.
// These are read-only in the form — the underlying must be an existing stock.
function onUnderlyingSelected(inst: Instrument | null) {
  if (inst) {
    optionModel.value.underlying_symbol = inst.symbol
    optionModel.value.currency = inst.currency
    optionModel.value.underlying_exchange = inst.exchange ?? ''
  } else {
    optionModel.value.underlying_symbol = ''
    optionModel.value.currency = null
    optionModel.value.underlying_exchange = ''
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
    let payload: StockCreate | OptionCreate | ForexCreate
    if (activeKind.value === 'stock') {
      payload = {
        kind: 'stock',
        symbol: stockModel.value.symbol,
        currency: stockModel.value.currency!,
      }
      if (stockModel.value.exchange) payload.exchange = stockModel.value.exchange
    } else if (activeKind.value === 'option') {
      payload = {
        kind: 'option',
        underlying_symbol: optionModel.value.underlying_symbol,
        currency: optionModel.value.currency!,
        opt_type: optionModel.value.opt_type as 'call' | 'put',
        strike: Number(optionModel.value.strike),
        expiry: formatDate(optionModel.value.expiry!),
        multiplier: optionModel.value.multiplier,
        style: optionModel.value.style,
      }
      if (optionModel.value.underlying_exchange) payload.underlying_exchange = optionModel.value.underlying_exchange
    } else {
      payload = {
        kind: 'forex',
        symbol: forexModel.value.symbol,
        base_currency: forexModel.value.base_currency!,
        quote_currency: forexModel.value.quote_currency!,
        pip_size: Number(forexModel.value.pip_size),
      }
      if (forexModel.value.contract_size) {
        const cs = Number(forexModel.value.contract_size)
        if (Number.isFinite(cs) && cs > 0) payload.contract_size = cs
      }
    }

    const { instrument, existed } = await instrumentsApi.create(payload)
    if (existed) {
      message.info(`Instrument ${instrument.symbol} already exists — selected`)
    } else {
      message.success(`Created ${instrument.symbol}`)
    }
    emit('saved', instrument)
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

function formatDate(ts: number): string {
  const d = new Date(ts)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
</script>

<template>
  <n-modal
    :show="show"
    title="New Instrument"
    preset="card"
    style="max-width: 560px;"
    :mask-closable="!submitting"
    @update:show="emit('update:show', $event)"
  >
    <n-radio-group v-model:value="activeKind" style="margin-bottom: 1rem;">
      <n-radio-button
        v-for="tab in kindTabs"
        :key="tab.value"
        :value="tab.value"
        :label="tab.label"
        :disabled="!!lockedKind && tab.value !== lockedKind"
      />
    </n-radio-group>

    <n-form ref="formRef" :model="currentModel" :rules="currentRules" label-placement="top">
      <!-- Stock fields -->
      <template v-if="activeKind === 'stock'">
        <n-form-item label="Symbol" path="symbol">
          <n-input v-model:value="stockModel.symbol" placeholder="e.g. AAPL" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Exchange" path="exchange">
          <n-input v-model:value="stockModel.exchange" placeholder="e.g. NASDAQ (optional)" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Currency" path="currency">
          <CurrencySelect v-model:model-value="stockModel.currency" :disabled="submitting" />
        </n-form-item>
      </template>

      <!-- Option fields -->
      <template v-if="activeKind === 'option'">
        <n-form-item label="Underlying Stock" path="underlying_instrument_id">
          <InstrumentPicker
            v-model:model-value="optionModel.underlying_instrument_id"
            kind="stock"
            allow-create
            placeholder="Select an existing stock (or create one)…"
            :disabled="submitting"
            @update:instrument="onUnderlyingSelected"
          />
        </n-form-item>
        <n-form-item label="Currency">
          <n-input
            :value="optionModel.currency ?? ''"
            placeholder="From selected stock"
            disabled
          />
        </n-form-item>
        <n-form-item label="Underlying Exchange">
          <n-input
            :value="optionModel.underlying_exchange || '—'"
            placeholder="From selected stock"
            disabled
          />
        </n-form-item>
        <n-form-item label="Option Type" path="opt_type">
          <n-select v-model:value="optionModel.opt_type" :options="optTypeOptions" placeholder="Call or Put" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Strike" path="strike">
          <n-input v-model:value="optionModel.strike" placeholder="e.g. 220" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Expiry" path="expiry">
          <n-date-picker v-model:value="optionModel.expiry" type="date" style="width: 100%;" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Multiplier" path="multiplier">
          <n-input-number v-model:value="optionModel.multiplier" :min="1" style="width: 100%;" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Style" path="style">
          <n-select v-model:value="optionModel.style" :options="styleOptions" :disabled="submitting" />
        </n-form-item>
      </template>

      <!-- Forex fields -->
      <template v-if="activeKind === 'forex'">
        <n-form-item label="Symbol" path="symbol">
          <n-input v-model:value="forexModel.symbol" placeholder="e.g. EURUSD" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Base Currency" path="base_currency">
          <CurrencySelect v-model:model-value="forexModel.base_currency" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Quote Currency" path="quote_currency">
          <CurrencySelect v-model:model-value="forexModel.quote_currency" :disabled="submitting" />
        </n-form-item>
        <n-text depth="3" style="font-size: 0.8rem; display: block; margin: -0.5rem 0 0.75rem;">
          Auto-filled from symbol; edit if needed for non-standard pairs.
        </n-text>
        <n-form-item label="Pip Size" path="pip_size">
          <n-input v-model:value="forexModel.pip_size" placeholder="e.g. 0.0001" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Contract Size" path="contract_size">
          <n-input v-model:value="forexModel.contract_size" placeholder="Optional, e.g. 100000" :disabled="submitting" />
        </n-form-item>
      </template>
    </n-form>

    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
        <n-button type="primary" @click="handleSubmit" :loading="submitting">Create</n-button>
      </div>
    </template>
  </n-modal>
</template>
