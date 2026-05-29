<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { type Trade } from '../api/trades'
import { type Instrument, instrumentsApi } from '../api/instruments'
import { useTrades } from '../composables/useTrades'
import { detectPattern, type PatternBadge } from '../utils/tradePatternBadge'
import TradeActionBadge from './TradeActionBadge.vue'
import TradeEntryModal from './TradeEntryModal.vue'

const props = withDefaults(defineProps<{
  positionId: string
  accountId: string
  currency?: string
  readonly?: boolean
}>(), {
  readonly: false,
})

const emit = defineEmits<{
  (e: 'trade-saved'): void
}>()

const message = useMessage()
const { trades, loading, error, includeArchived, refresh, archive, updateNotes } = useTrades(props.positionId)
const instrumentMap = ref<Record<string, Instrument>>({})
const showTradeModal = ref(false)

// Notes editing state
const editingNotesId = ref<string | null>(null)
const editingNotesValue = ref('')
const editingNotesLoading = ref(false)

async function loadInstruments() {
  const ids = [...new Set(trades.value.map(t => t.instrument_id))]
  const map: Record<string, Instrument> = {}
  for (const id of ids) {
    if (!instrumentMap.value[id]) {
      try { map[id] = await instrumentsApi.get(id) } catch { /* skip */ }
    }
  }
  if (Object.keys(map).length > 0) {
    instrumentMap.value = { ...instrumentMap.value, ...map }
  }
}

onMounted(async () => {
  await refresh()
  await loadInstruments()
})

watch(trades, () => { void loadInstruments() })

// Cancel in-progress notes editing when readonly switches on
watch(() => props.readonly, (val) => {
  if (val) cancelEditNotes()
})

// Group trades by order_group_id
interface TradeGroup {
  groupId: string | null
  key: string
  trades: Trade[]
  pattern: PatternBadge
}

const groups = computed<TradeGroup[]>(() => {
  const map = new Map<string, Trade[]>()
  for (const t of trades.value) {
    // NULL order_group_id → each trade is its own visual group
    const key = t.order_group_id ?? t.id
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(t)
  }
  return Array.from(map.entries()).map(([key, groupTrades]) => ({
    groupId: groupTrades[0]?.order_group_id ?? null,
    key,
    trades: groupTrades.sort((a, b) => new Date(a.executed_at).getTime() - new Date(b.executed_at).getTime()),
    pattern: detectPattern(groupTrades, instrumentMap.value),
  }))
})

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatNum(val: string | number | null): string {
  if (val == null) return '—'
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(val))
}

function instrumentSymbol(id: string): string {
  return instrumentMap.value[id]?.symbol ?? id.slice(0, 8)
}

function patternLabel(badge: PatternBadge): string {
  const map: Record<string, string> = {
    'ic-open': 'IC-Open',
    assignment: 'Assignment',
    exercise: 'Exercise',
    expiration: 'Expiration',
  }
  return badge ? map[badge] ?? '' : ''
}

function patternColor(badge: PatternBadge): 'info' | 'warning' | 'default' {
  if (badge === 'ic-open') return 'info'
  if (badge === 'assignment' || badge === 'exercise') return 'warning'
  return 'default'
}

function patternTooltip(badge: PatternBadge): string {
  const map: Record<string, string> = {
    'ic-open': 'Iron Condor opened (4 option legs in one order)',
    assignment: 'Assignment: short option closed, stock leg created',
    exercise: 'Exercise: long option closed, stock leg created',
    expiration: 'Option expired worthless (price=0)',
  }
  return badge ? map[badge] ?? '' : ''
}

async function handleArchive(id: string) {
  if (props.readonly) return
  try {
    await archive(id)
    message.success('Trade archived')
  } catch (err) {
    message.error('Failed to archive trade')
  }
}

function startEditNotes(trade: Trade) {
  if (trade.archived_at || props.readonly) return
  editingNotesId.value = trade.id
  editingNotesValue.value = trade.notes ?? ''
}

function cancelEditNotes() {
  editingNotesId.value = null
  editingNotesValue.value = ''
}

async function saveEditNotes(id: string) {
  if (props.readonly) {
    cancelEditNotes()
    return
  }
  editingNotesLoading.value = true
  try {
    await updateNotes(id, editingNotesValue.value || null)
    message.success('Notes updated')
    editingNotesId.value = null
    editingNotesValue.value = ''
  } catch {
    message.error('Failed to update notes')
  } finally {
    editingNotesLoading.value = false
  }
}

function handleTradeSaved() {
  showTradeModal.value = false
  void refresh()
  emit('trade-saved')
}

defineExpose({ refresh })
</script>

<template>
  <div>
    <!-- Header strip -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <n-switch v-model:value="includeArchived" size="small" />
        <n-text depth="3" style="font-size: 0.85rem;">Show archived</n-text>
      </div>
      <n-button type="primary" size="small" :disabled="readonly" @click="showTradeModal = true">+ New Trade</n-button>
    </div>

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" style="margin-bottom: 1rem;">
        {{ error }}
        <n-button size="small" @click="refresh" style="margin-left: 0.5rem;">Retry</n-button>
      </n-alert>

      <template v-if="groups.length === 0 && !loading">
        <n-empty description="No trades yet on this position.">
          <template #extra>
            <n-button size="small" :disabled="readonly" @click="showTradeModal = true">+ New Trade</n-button>
          </template>
        </n-empty>
      </template>

      <template v-else>
        <n-list bordered>
          <n-list-item v-for="group in groups" :key="group.key">
            <!-- Group header -->
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
              <n-tag v-if="group.pattern" :type="patternColor(group.pattern)" size="small">
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span>{{ patternLabel(group.pattern) }}</span>
                  </template>
                  {{ patternTooltip(group.pattern) }}
                </n-tooltip>
              </n-tag>
              <n-text depth="3" style="font-size: 0.85rem;">
                {{ formatDateTime(group.trades[0].executed_at) }}
              </n-text>
              <n-tag v-if="group.trades.length > 1" size="small" :bordered="false">{{ group.trades.length }} legs</n-tag>
            </div>

            <!-- Group rows as a small table -->
            <n-table :bordered="false" :single-line="false" size="small" striped>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Instrument</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Cash Flow</th>
                  <th>Comm+Fees</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trade in group.trades" :key="trade.id" :style="{ opacity: trade.archived_at ? 0.5 : 1 }">
                  <td><TradeActionBadge :action="trade.action" /></td>
                  <td>{{ instrumentSymbol(trade.instrument_id) }}</td>
                  <td>{{ formatNum(trade.quantity) }}</td>
                  <td>{{ formatNum(trade.price) }}</td>
                  <td>
                    <span :style="{ color: Number(trade.cash_flow) > 0 ? '#18a058' : Number(trade.cash_flow) < 0 ? '#d03050' : undefined, fontWeight: 500 }">
                      {{ formatNum(trade.cash_flow) }}
                    </span>
                  </td>
                  <td>{{ formatNum(Number(trade.commission) + Number(trade.fees)) }}</td>
                  <td>
                    <div style="display: flex; gap: 0.25rem; flex-wrap: nowrap;">
                      <!-- Edit notes -->
                      <template v-if="editingNotesId === trade.id">
                        <n-input
                          v-model:value="editingNotesValue"
                          size="tiny"
                          placeholder="Notes..."
                          style="width: 140px;"
                          :loading="editingNotesLoading"
                          @keyup.enter="saveEditNotes(trade.id)"
                        />
                        <n-button size="tiny" type="primary" @click="saveEditNotes(trade.id)" :loading="editingNotesLoading">Save</n-button>
                        <n-button size="tiny" @click="cancelEditNotes">Cancel</n-button>
                      </template>
                      <template v-else>
                        <n-button
                          size="tiny"
                          quaternary
                          :disabled="!!trade.archived_at || readonly"
                          @click="startEditNotes(trade)"
                        >
                          Edit notes
                        </n-button>
                        <n-popconfirm
                          v-if="!trade.archived_at && !readonly"
                          @positive-click="handleArchive(trade.id)"
                        >
                          <template #trigger>
                            <n-button size="tiny" quaternary type="warning">Archive</n-button>
                          </template>
                          Archive this trade? It will be excluded from position calculations.
                        </n-popconfirm>
                      </template>
                    </div>
                  </td>
                </tr>
              </tbody>
            </n-table>

            <!-- Group notes if any -->
            <div v-for="trade in group.trades" :key="'note-' + trade.id">
              <n-text v-if="trade.notes" depth="3" style="font-size: 0.8rem; display: block; margin-top: 0.25rem;">
                {{ instrumentSymbol(trade.instrument_id) }}: {{ trade.notes }}
              </n-text>
            </div>
          </n-list-item>
        </n-list>
      </template>
    </n-spin>

    <!-- Standalone TradeEntryModal -->
    <TradeEntryModal
      v-model:show="showTradeModal"
      :position-id="positionId"
      :account-id="accountId"
      :currency="currency"
      @saved="handleTradeSaved"
    />
  </div>
</template>
