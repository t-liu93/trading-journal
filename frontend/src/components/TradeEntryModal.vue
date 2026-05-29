<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { type TradeCreate } from '../api/trades'
import TradeLegRow from './TradeLegRow.vue'

const props = withDefaults(defineProps<{
  show?: boolean
  inline?: boolean
  positionId?: string
  accountId: string
  currency?: string
}>(), {
  show: false,
  inline: false,
  positionId: undefined,
  currency: '',
})

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
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
  for (const row of legRows.value) {
    const legRef = legRefs.value[row.id]
    if (!legRef) return false
    const err = legRef.validate()
    if (err) {
      message.warning(err)
      return false
    }
  }
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

defineExpose({ rows: legRows, validate, getRows, reset })
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
        @remove="removeLeg(row.id)"
      />
    </div>
    <n-button dashed block @click="addLeg" style="margin-bottom: 0.5rem;">
      + Add leg
    </n-button>
    <n-text depth="3" style="font-size: 0.75rem; display: block; margin-bottom: 0.5rem;">
      Cash flow previews are for display only. Server computes the authoritative values.
    </n-text>
  </template>

  <!-- Standalone mode: render as a modal -->
  <n-modal
    v-else
    :show="show"
    title="New Trade"
    preset="card"
    style="max-width: 700px;"
    :mask-closable="!submitting"
    @update:show="emit('update:show', $event)"
  >
    <div v-for="row in legRows" :key="row.id" style="margin-bottom: 0.5rem;">
      <TradeLegRow
        :ref="(el: any) => setLegRef(row.id, el)"
        :account-id="accountId"
        :removable="legRows.length > 1"
        :currency="currency"
        @remove="removeLeg(row.id)"
      />
    </div>
    <n-button dashed block @click="addLeg" :disabled="submitting" style="margin-bottom: 0.5rem;">
      + Add leg
    </n-button>
    <n-text depth="3" style="font-size: 0.75rem; display: block; margin-bottom: 0.5rem;">
      Cash flow previews are for display only. Server computes the authoritative values.
    </n-text>

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
