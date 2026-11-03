<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NButton, NCheckbox, type SelectOption, useMessage } from 'naive-ui'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'
import { formatInstrumentCode } from '../utils/instrumentLabel'
import InstrumentForm from './InstrumentForm.vue'

const PAGE_SIZE = 50
const props = withDefaults(defineProps<{
  modelValue: string | null
  kind?: InstrumentKind
  placeholder?: string
  allowCreate?: boolean
  disabled?: boolean
  optionUnderlyingId?: string | null
}>(), { placeholder: 'Search instrument…', allowCreate: false, disabled: false, optionUnderlyingId: null })

const emit = defineEmits<{
  (e: 'update:modelValue', id: string | null): void
  (e: 'update:instrument', instrument: Instrument | null): void
}>()
const message = useMessage()
const candidates = ref<Instrument[]>([])
const currentInstrument = ref<Instrument | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const includeExpired = ref(false)
const hasMore = ref(false)
const showCreateForm = ref(false)
const createQuery = ref('')
const searchQuery = ref('')
const options = computed<SelectOption[]>(() => {
  const rows: SelectOption[] = candidates.value.map((inst) => ({ label: formatInstrumentLabel(inst), value: inst.id }))
  if (props.allowCreate && searchQuery.value && candidates.value.length === 0 && !loading.value && !error.value) {
    rows.push({ label: `+ Create new instrument matching "${searchQuery.value}"`, value: '__create__' })
  }
  return rows
})
const fallbackOption = (value: string | number): SelectOption => ({
  label: currentInstrument.value?.id === String(value) ? formatInstrumentLabel(currentInstrument.value) : String(value),
  value,
})
const instrumentMap = new Map<string, Instrument>()
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let requestSeq = 0
let labelSeq = 0
let requestOffset = 0
let disposed = false
let isOpen = false

function formatInstrumentLabel(inst: Instrument): string {
  if (inst.kind === 'option' && inst.option) return formatInstrumentCode(inst)
  const suffix = inst.exchange ? ` (${inst.exchange})` : ''
  return `${inst.symbol}${suffix} [${inst.kind}]`
}

function invalidate(clearCandidates = true) {
  requestSeq += 1
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = null
  loading.value = false
  error.value = null
  hasMore.value = false
  if (clearCandidates) {
    candidates.value = []
    requestOffset = 0
  }
}

async function loadPage(q: string, append: boolean) {
  const seq = ++requestSeq
  const offset = append ? requestOffset : 0
  loading.value = true
  error.value = null
  try {
    const results = await instrumentsApi.list({
      q: q || undefined, kind: props.kind, limit: PAGE_SIZE + 1, offset,
      include_expired: includeExpired.value, option_underlying_id: props.optionUnderlyingId ?? undefined,
    })
    if (seq !== requestSeq || disposed) return
    const page = results.slice(0, PAGE_SIZE)
    for (const inst of page) instrumentMap.set(inst.id, inst)
    if (append) {
      const ids = new Set(candidates.value.map((item) => item.id))
      candidates.value = [...candidates.value, ...page.filter((item) => !ids.has(item.id))]
    } else candidates.value = page
    requestOffset = offset + PAGE_SIZE
    hasMore.value = results.length > PAGE_SIZE
  } catch (err) {
    if (seq === requestSeq && !disposed) {
      error.value = err instanceof Error ? err.message : 'Failed to load instruments.'
    }
  } finally {
    if (seq === requestSeq && !disposed) loading.value = false
  }
}

function scheduleSearch(q: string) {
  createQuery.value = q
  searchQuery.value = q
  invalidate()
  const seq = requestSeq
  debounceTimer = setTimeout(() => {
    if (seq === requestSeq && !disposed) void loadPage(q, false)
  }, 300)
}

function handleSearch(q: string) { scheduleSearch(q) }
function handleFocus() {
  if (!props.disabled && !isOpen) {
    isOpen = true
    invalidate()
    void loadPage(searchQuery.value, false)
    if (props.modelValue) void resolveCurrent(props.modelValue)
  }
}
function handleShowChange(show: boolean) {
  if (!show) {
    isOpen = false
  } else if (!props.disabled && !isOpen) {
    isOpen = true
    invalidate()
    void loadPage(searchQuery.value, false)
    if (props.modelValue) void resolveCurrent(props.modelValue)
  }
}
function loadMore() {
  if (!loading.value && hasMore.value) void loadPage(searchQuery.value, true)
}
function retry() {
  if (requestOffset > 0 && candidates.value.length > 0) void loadPage(searchQuery.value, true)
  else void loadPage(searchQuery.value, false)
}
function handleUpdateValue(val: string | null) {
  if (val === '__create__') { showCreateForm.value = true; return }
  const instrument = val ? instrumentMap.get(val) ?? currentInstrument.value : null
  if (instrument && props.kind && instrument.kind !== props.kind) {
    message.error(`Expected a ${props.kind} instrument`)
    return
  }
  currentInstrument.value = instrument
  emit('update:modelValue', val)
  emit('update:instrument', instrument)
}
function handleInstrumentSaved(instrument: Instrument) {
  if (props.kind && instrument.kind !== props.kind) {
    message.error(`Expected a ${props.kind} instrument`)
    return
  }
  instrumentMap.set(instrument.id, instrument)
  currentInstrument.value = instrument
  const isExpiredOption = instrument.kind === 'option'
    && Boolean(instrument.option?.expiry && instrument.option.expiry < new Date().toISOString().slice(0, 10))
  if (isExpiredOption && !includeExpired.value) {
    includeExpired.value = true
    message.info('Expired options are now shown for this picker. Refreshing the candidates.')
    if (!isOpen) {
      invalidate()
      void loadPage(searchQuery.value, false)
    }
  } else {
    candidates.value = [...candidates.value.filter((item) => item.id !== instrument.id), instrument]
  }
  emit('update:modelValue', instrument.id)
  emit('update:instrument', instrument)
  showCreateForm.value = false
}
async function resolveCurrent(id: string) {
  const seq = ++labelSeq
  if (instrumentMap.has(id)) { currentInstrument.value = instrumentMap.get(id) ?? null; return }
  try {
    const instrument = await instrumentsApi.get(id)
    if (seq === labelSeq && !disposed && props.modelValue === id) {
      instrumentMap.set(id, instrument)
      currentInstrument.value = instrument
    }
  } catch {
    // Keep the ID selected; a later focus or prop update retries the label lookup.
  }
}

watch(() => props.kind, () => {
  invalidate()
  searchQuery.value = ''
  if (isOpen) void loadPage('', false)
})
watch(() => props.optionUnderlyingId, () => {
  invalidate()
  if (isOpen) void loadPage(searchQuery.value, false)
})
watch(() => props.modelValue, (id) => {
  if (!id) { currentInstrument.value = null; return }
  void resolveCurrent(id)
}, { immediate: true })
watch(includeExpired, () => {
  invalidate()
  if (isOpen) void loadPage(searchQuery.value, false)
})
onBeforeUnmount(() => { disposed = true; invalidate() })
</script>

<template>
  <div class="instrument-picker">
    <n-select
      :value="modelValue" :options="options" :fallback-option="fallbackOption" :placeholder="placeholder" :loading="loading"
      :disabled="disabled" filterable remote clearable @search="handleSearch"
      @update:value="handleUpdateValue" @focus="handleFocus" @update:show="handleShowChange"
    >
      <template #action>
        <div v-if="error" class="picker-status" role="alert">
          <span>{{ error }}</span><NButton size="tiny" @click="retry">Retry</NButton>
        </div>
        <div v-else-if="!loading && candidates.length === 0" class="picker-status" role="status">No instruments found.</div>
        <NButton v-if="hasMore" size="tiny" :loading="loading" @click="loadMore">Load more</NButton>
      </template>
    </n-select>
    <n-checkbox v-if="kind === 'option' || !kind" v-model:checked="includeExpired">Show expired options</n-checkbox>
    <InstrumentForm v-if="allowCreate" :show="showCreateForm" :initial-kind="kind"
      :initial-symbol="createQuery" :locked-kind="kind" @update:show="showCreateForm = $event"
      @saved="handleInstrumentSaved" />
  </div>
</template>

<style scoped>
.instrument-picker { display: grid; gap: 0.35rem; }
.picker-status { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
</style>
