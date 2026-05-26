<script setup lang="ts">
import { ref, watch } from 'vue'
import { type SelectOption } from 'naive-ui'
import { type Instrument, type InstrumentKind, instrumentsApi } from '../api/instruments'

const props = withDefaults(defineProps<{
  modelValue: string | null
  kind?: InstrumentKind
  placeholder?: string
}>(), {
  placeholder: 'Search instrument…',
})

const emit = defineEmits<{
  (e: 'update:modelValue', id: string | null): void
}>()

const options = ref<SelectOption[]>([])
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

function instrumentsToOptions(items: Instrument[]): SelectOption[] {
  return items.map((inst) => ({
    label: inst.symbol + (inst.exchange ? ` (${inst.exchange})` : ''),
    value: inst.id,
  }))
}

async function search(q: string) {
  if (!q || q.length < 1) {
    ++searchSeq
    loading.value = false
    options.value = []
    return
  }
  const seq = ++searchSeq
  loading.value = true
  try {
    const results = await instrumentsApi.list({
      q,
      kind: props.kind,
    })
    if (seq === searchSeq) {
      options.value = instrumentsToOptions(results)
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
  if (debounceTimer) clearTimeout(debounceTimer)
  if (!q) {
    ++searchSeq
    loading.value = false
    options.value = []
    return
  }
  debounceTimer = setTimeout(() => void search(q), 300)
}

function handleUpdateValue(val: string | null) {
  emit('update:modelValue', val)
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
    filterable
    remote
    clearable
    @search="handleSearch"
    @update:value="handleUpdateValue"
  />
</template>
