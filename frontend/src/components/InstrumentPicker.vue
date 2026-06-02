<script setup lang="ts">
import { ref, watch } from 'vue'
import { type SelectOption, useMessage } from 'naive-ui'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'
import { formatInstrumentCode } from '../utils/instrumentLabel'
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
  (e: 'update:instrument', instrument: Instrument | null): void
}>()

const message = useMessage()
const options = ref<SelectOption[]>([])
// Cache of loaded instruments by id, so we can hand the full object back to
// the parent on selection (used e.g. to derive an option's underlying currency).
const instrumentMap = new Map<string, Instrument>()
const loading = ref(false)
const showCreateForm = ref(false)
const createQuery = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

function formatInstrumentLabel(inst: Instrument): string {
  if (inst.kind === 'option' && inst.option) {
    return formatInstrumentCode(inst)
  }
  const suffix = inst.exchange ? ` (${inst.exchange})` : ''
  return `${inst.symbol}${suffix} [${inst.kind}]`
}

function instrumentsToOptions(items: Instrument[]): SelectOption[] {
  return items.map((inst) => {
    instrumentMap.set(inst.id, inst)
    return {
      label: formatInstrumentLabel(inst),
      value: inst.id,
    }
  })
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
  const instrument = val ? instrumentMap.get(val) ?? null : null
  if (instrument && props.kind && instrument.kind !== props.kind) {
    message.error(`Expected a ${props.kind} instrument`)
    return
  }
  emit('update:modelValue', val)
  emit('update:instrument', instrument)
}

function handleInstrumentSaved(instrument: Instrument) {
  if (props.kind && instrument.kind !== props.kind) {
    message.error(`Expected a ${props.kind} instrument`)
    return
  }
  // Upsert into local options so the picker shows the label immediately
  instrumentMap.set(instrument.id, instrument)
  const existing = options.value.find((o) => o.value === instrument.id)
  const opt = { label: formatInstrumentLabel(instrument), value: instrument.id }
  if (existing) {
    existing.label = opt.label
  } else {
    options.value.push(opt)
  }
  emit('update:modelValue', instrument.id)
  emit('update:instrument', instrument)
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
    :locked-kind="kind"
    @update:show="showCreateForm = $event"
    @saved="handleInstrumentSaved"
  />
</template>
