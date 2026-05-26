<script setup lang="ts">
defineProps<{
  modelValue: string | null
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void
}>()

const options = [
  { label: 'USD', value: 'USD' },
  { label: 'EUR', value: 'EUR' },
  { label: 'GBP', value: 'GBP' },
  { label: 'JPY', value: 'JPY' },
  { label: 'CHF', value: 'CHF' },
  { label: 'CAD', value: 'CAD' },
  { label: 'AUD', value: 'AUD' },
  { label: 'HKD', value: 'HKD' },
]

function handleUpdate(value: string | null) {
  emit('update:modelValue', value ? value.toUpperCase() : null)
}
</script>

<template>
  <n-select
    :value="modelValue"
    :options="options"
    :placeholder="placeholder ?? 'Select or type currency code'"
    filterable
    tag
    :disabled="disabled"
    @update:value="handleUpdate"
  />
</template>
