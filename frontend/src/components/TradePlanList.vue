<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useTradePlans } from '../composables/useTradePlans'

const props = defineProps<{ positionId: string }>()
const emit = defineEmits<{ (e: 'loaded', isEmpty: boolean): void }>()

const { revisions, current, loading, refresh } = useTradePlans(ref(props.positionId))

onMounted(async () => {
  await refresh()
  emit('loaded', revisions.value.length === 0)
})

async function doRefresh() {
  await refresh()
  emit('loaded', revisions.value.length === 0)
}

defineExpose({ refresh: doRefresh, revisions })

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatNum(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—'
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(val))
}
</script>

<template>
  <n-spin :show="loading">
    <template v-if="revisions.length === 0">
      <n-empty description="No plan revisions yet" style="margin: 1.5rem 0;" />
    </template>
    <template v-else>
      <n-timeline>
        <n-timeline-item
          v-for="rev in revisions"
          :key="rev.revision_no"
          :type="rev === current ? 'success' : 'default'"
        >
          <template #header>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span>Revision {{ rev.revision_no }}</span>
              <n-tag v-if="rev === current" type="success" size="small">Current</n-tag>
            </div>
          </template>
          <n-descriptions label-placement="left" :column="1" bordered size="small">
            <n-descriptions-item label="Effective At">{{ formatDateTime(rev.effective_at) }}</n-descriptions-item>
            <n-descriptions-item v-if="rev.planned_entry" label="Planned Entry">{{ formatNum(rev.planned_entry) }}</n-descriptions-item>
            <n-descriptions-item v-if="rev.planned_stop_loss" label="Planned Stop Loss">{{ formatNum(rev.planned_stop_loss) }}</n-descriptions-item>
            <n-descriptions-item v-if="rev.planned_take_profit" label="Planned Take Profit">{{ formatNum(rev.planned_take_profit) }}</n-descriptions-item>
            <n-descriptions-item v-if="rev.target_rr" label="Target R:R">{{ formatNum(rev.target_rr) }}</n-descriptions-item>
            <n-descriptions-item v-if="rev.thesis" label="Thesis">
              <n-ellipsis :line-clamp="3" :tooltip="{ width: 400 }">{{ rev.thesis }}</n-ellipsis>
            </n-descriptions-item>
          </n-descriptions>
        </n-timeline-item>
      </n-timeline>
    </template>
  </n-spin>
</template>
