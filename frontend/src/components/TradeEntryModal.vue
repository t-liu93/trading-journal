<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { type TradeCreate } from '../api/trades'
import { ApiError } from '../api/types'
import TradeLegRow from './TradeLegRow.vue'
import type { Instrument } from '../api/instruments'

const props = withDefaults(defineProps<{
  show?: boolean
  inline?: boolean
  positionId?: string
  accountId: string
  currency?: string
  primaryInstrument?: Instrument | null
  optionUnderlyingInstrument?: Instrument | null
  primaryInstrumentLoading?: boolean
  primaryInstrumentError?: string | null
}>(), {
  show: false,
  inline: false,
  positionId: undefined,
  currency: '',
  primaryInstrument: null,
  optionUnderlyingInstrument: null,
  primaryInstrumentLoading: false,
  primaryInstrumentError: null,
})

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
  (e: 'retry-primary-instrument'): void
}>()

const message = useMessage()
const submitting = ref(false)

interface LegRowState {
  id: number
}

let nextRowId = 1
const legRows = ref<LegRowState[]>([{ id: nextRowId++ }])
const legRefs = ref<Record<number, InstanceType<typeof TradeLegRow>>>({})

function setLegRef(id: number, el: InstanceType<typeof TradeLegRow> | null) {
  if (el) legRefs.value[id] = el
}

function addLeg() {
  legRows.value.push({ id: nextRowId++ })
}

function removeLeg(id: number) {
  if (legRows.value.length <= 1) return
  legRows.value = legRows.value.filter(r => r.id !== id)
  delete legRefs.value[id]
}

function getRows(): TradeCreate[] {
  return legRows.value
    .map(r => legRefs.value[r.id])
    .filter((ref): ref is InstanceType<typeof TradeLegRow> => ref != null)
    .map(ref => ref.toPayload(props.positionId))
}

function validate(): boolean {
  for (const [index, row] of legRows.value.entries()) {
    const legRef = legRefs.value[row.id]
    if (!legRef) return false
    const err = legRef.validate()
    if (err) {
      message.warning(`Leg ${index + 1}: ${err}`)
      void legRef.focusValidationError()
      return false
    }
  }
  return true
}

function showApiError(error: unknown): boolean {
  if (!(error instanceof ApiError) || !Array.isArray(error.detail)) return false
  const fieldMap: Record<string, 'instrument' | 'action' | 'quantity' | 'price' | 'commission' | 'fees' | 'executed_at'> = {
    instrument_id: 'instrument', action: 'action', quantity: 'quantity', price: 'price',
    commission: 'commission', fees: 'fees', executed_at: 'executed_at',
  }
  const first = error.detail.find((item): item is { loc: unknown[]; msg?: unknown } =>
    !!item && typeof item === 'object' && 'loc' in item && Array.isArray((item as { loc?: unknown }).loc),
  )
  if (!first) return false
  const parts = first.loc
  let fieldName: string | undefined
  for (const part of parts) if (typeof part === 'string' && part in fieldMap) fieldName = part
  if (typeof fieldName !== 'string') return false
  const rowIndex = parts.find(part => typeof part === 'number')
  const row = legRows.value[typeof rowIndex === 'number' ? rowIndex : 0]
  const leg = row ? legRefs.value[row.id] : undefined
  if (!leg) return false
  const messageText = typeof first.msg === 'string' ? first.msg : 'Check this trade value.'
  leg.showServerError(fieldMap[fieldName]!, messageText)
  void leg.focusValidationError()
  return true
}

function reset() {
  legRows.value = [{ id: nextRowId++ }]
  legRefs.value = {}
}

async function handleSubmit() {
  if (!props.positionId) return
  if (!validate()) return

  submitting.value = true
  try {
    const payloads = getRows()
    if (payloads.length === 0) {
      message.error('At least one leg is required')
      return
    }

    // Import dynamically to avoid circular deps
    const { tradesApi } = await import('../api/trades')
    if (payloads.length === 1) {
      await tradesApi.create(payloads[0])
    } else {
      await tradesApi.createMany(payloads)
    }
    message.success('Trade(s) created')
    reset()
    emit('saved')
    if (!props.inline) emit('update:show', false)
  } catch (err) {
    const { ApiError } = await import('../api/types')
    if (err instanceof ApiError) {
      showApiError(err)
      message.error(err.message)
    } else {
      message.error('Failed to create trade(s)')
    }
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('update:show', false)
}

defineExpose({ rows: legRows, validate, getRows, reset, showApiError })
</script>

<template>
  <!-- Inline mode: just render the leg rows without a modal -->
  <template v-if="inline">
    <div v-for="row in legRows" :key="row.id" style="margin-bottom: 0.5rem;">
      <TradeLegRow
        :ref="(el: any) => setLegRef(row.id, el)"
        :account-id="accountId"
        :removable="legRows.length > 1"
        :currency="currency"
        :primary-instrument="primaryInstrument"
        :option-underlying-instrument="optionUnderlyingInstrument"
        :primary-instrument-loading="primaryInstrumentLoading"
        :primary-instrument-error="primaryInstrumentError"
        @remove="removeLeg(row.id)"
      />
    </div>
    <n-button dashed block @click="addLeg" style="margin-bottom: 0.5rem;">
      + Add leg
    </n-button>
      <n-text depth="3" style="font-size: 0.75rem; display: block; margin-bottom: 0.5rem;">
      Cash flow previews estimate the amount received or paid for each trade after costs.
    </n-text>
    <n-alert v-if="primaryInstrumentLoading" type="info" :bordered="false" style="margin-bottom: 0.5rem;">Loading primary instrument context. Option selection is paused.</n-alert>
    <n-alert v-else-if="primaryInstrumentError" type="error" :bordered="false" style="margin-bottom: 0.5rem;">
      {{ primaryInstrumentError }} <n-button size="tiny" @click="emit('retry-primary-instrument')">Retry</n-button>
    </n-alert>
  </template>

  <!-- Standalone mode: render as a modal -->
  <n-modal
    v-else
    :show="show"
    title="New Trade"
    preset="card"
    style="width: min(700px, calc(100vw - 24px)); max-width: 700px;"
    :mask-closable="!submitting"
    @update:show="emit('update:show', $event)"
  >
    <div v-for="row in legRows" :key="row.id" style="margin-bottom: 0.5rem;">
      <TradeLegRow
        :ref="(el: any) => setLegRef(row.id, el)"
        :account-id="accountId"
        :removable="legRows.length > 1"
        :currency="currency"
        :primary-instrument="primaryInstrument"
        :option-underlying-instrument="optionUnderlyingInstrument"
        :primary-instrument-loading="primaryInstrumentLoading"
        :primary-instrument-error="primaryInstrumentError"
        @remove="removeLeg(row.id)"
      />
    </div>
    <n-button dashed block @click="addLeg" :disabled="submitting" style="margin-bottom: 0.5rem;">
      + Add leg
    </n-button>
      <n-text depth="3" style="font-size: 0.75rem; display: block; margin-bottom: 0.5rem;">
      Cash flow previews estimate the amount received or paid for each trade after costs.
    </n-text>
    <n-alert v-if="primaryInstrumentLoading" type="info" :bordered="false" style="margin-bottom: 0.5rem;">Loading primary instrument context. Option selection is paused.</n-alert>
    <n-alert v-else-if="primaryInstrumentError" type="error" :bordered="false" style="margin-bottom: 0.5rem;">
      {{ primaryInstrumentError }} <n-button size="tiny" @click="emit('retry-primary-instrument')">Retry</n-button>
    </n-alert>

    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
        <n-button type="primary" @click="handleSubmit" :loading="submitting">
          Submit
        </n-button>
      </div>
    </template>
  </n-modal>
</template>
