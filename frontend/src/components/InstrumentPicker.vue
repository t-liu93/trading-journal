<script setup lang="ts">
import { ref, watch } from 'vue'
import { type SelectOption } from 'naive-ui'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'
import InstrumentForm from './InstrumentForm.vue'

const props = withDefaults(defineProps<{
  modelValue: string | null
  kind?: InstrumentKind
  placeholder?: string
  allowCreate?: boolean
  disabled?: boolean
}>(), {
  placeholder: 'Search instrument…',
  allowCreate: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', id: string | null): void
}>()

const options = ref<SelectOption[]>([])
const loading = ref(false)
const showCreateForm = ref(false)
const createQuery = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

function formatInstrumentLabel(inst: Instrument): string {
  if (inst.kind === 'option' && inst.option) {
    const o = inst.option
    const typeLetter = o.opt_type === 'call' ? 'C' : 'P'
    const strike = Number(o.strike).toFixed(2)
    const d = new Date(o.expiry)
    const yy = String(d.getFullYear()).slice(-2)
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${inst.symbol}${strike}${typeLetter}${yy}${mm}${dd}`
  }
  const suffix = inst.exchange ? ` (${inst.exchange})` : ''
  return `${inst.symbol}${suffix} [${inst.kind}]`
}

function instrumentsToOptions(items: Instrument[]): SelectOption[] {
  return items.map((inst) => ({
    label: formatInstrumentLabel(inst),
    value: inst.id,
  }))
}

async function search(q: string) {
  const seq = ++searchSeq
  loading.value = true
  try {
    const results = await instrumentsApi.list({
      q: q || undefined,
      kind: props.kind,
    })
    if (seq === searchSeq) {
      const opts = instrumentsToOptions(results)
      if (props.allowCreate && q && results.length === 0) {
        opts.push({
          label: `+ Create new instrument matching "${q}"`,
          value: '__create__',
        })
      }
      options.value = opts
    }
  } catch {
    if (seq === searchSeq) {
      options.value = []
    }
  } finally {
    if (seq === searchSeq) {
      loading.value = false
    }
  }
}

function handleSearch(q: string) {
  createQuery.value = q
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => void search(q), 300)
}

function handleUpdateValue(val: string | null) {
  if (val === '__create__') {
    showCreateForm.value = true
    return
  }
  emit('update:modelValue', val)
}

function handleInstrumentSaved(instrument: Instrument) {
  // Upsert into local options so the picker shows the label immediately
  const existing = options.value.find((o) => o.value === instrument.id)
  const opt = { label: formatInstrumentLabel(instrument), value: instrument.id }
  if (existing) {
    existing.label = opt.label
  } else {
    options.value.push(opt)
  }
  emit('update:modelValue', instrument.id)
  showCreateForm.value = false
}

watch(() => props.kind, () => {
  ++searchSeq
  if (debounceTimer) clearTimeout(debounceTimer)
  loading.value = false
  options.value = []
})
</script>

<template>
  <n-select
    :value="modelValue"
    :options="options"
    :placeholder="placeholder"
    :loading="loading"
    :disabled="disabled"
    filterable
    remote
    clearable
    @search="handleSearch"
    @update:value="handleUpdateValue"
    @focus="!disabled && search('')"
  />
  <InstrumentForm
    v-if="allowCreate"
    :show="showCreateForm"
    :initial-kind="kind"
    :initial-symbol="createQuery"
    @update:show="showCreateForm = $event"
    @saved="handleInstrumentSaved"
  />
</template>
