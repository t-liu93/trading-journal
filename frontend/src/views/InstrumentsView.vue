<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { type DataTableColumns, NTag, NText } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import InstrumentForm from '../components/InstrumentForm.vue'
import { useInstruments } from '../composables/useInstruments'
import { type Instrument, type InstrumentKind } from '../api/instruments'

const { instruments, loading, error, kindFilter, query, refresh } = useInstruments()

onMounted(refresh)

const kindOptions = [
  { label: 'All', value: '' },
  { label: 'Stock', value: 'stock' },
  { label: 'Option', value: 'option' },
  { label: 'Forex', value: 'forex' },
]

const modalShow = ref(false)

function openCreate() {
  modalShow.value = true
}

function onSaved() {
  void refresh()
}

const dateFmt = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
})

function kindTagColor(kind: InstrumentKind): 'success' | 'warning' | 'info' {
  if (kind === 'stock') return 'success'
  if (kind === 'option') return 'warning'
  return 'info'
}

const columns = computed<DataTableColumns<Instrument>>(() => [
  {
    title: 'Kind',
    key: 'kind',
    width: 100,
    render: (row) =>
      h(NTag, { size: 'small', type: kindTagColor(row.kind) }, () => row.kind),
  },
  { title: 'Symbol', key: 'symbol' },
  { title: 'Exchange', key: 'exchange', render: (row) => row.exchange ?? '' },
  { title: 'Currency', key: 'currency' },
  {
    title: 'Created',
    key: 'created_at',
    render: (row) => dateFmt.format(new Date(row.created_at)),
  },
])

function renderExpand(row: Instrument) {
  if (row.kind === 'stock') {
    return h(NText, { depth: 3 }, () => 'No additional fields for stock instruments.')
  }
  if (row.kind === 'option' && row.option) {
    const o = row.option
    return h(
      'div',
      { style: 'display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; padding: 0.5rem 0;' },
      [
        h(NText, { depth: 3 }, () => 'Type:'), h('span', {}, o.opt_type),
        h(NText, { depth: 3 }, () => 'Strike:'), h('span', {}, o.strike),
        h(NText, { depth: 3 }, () => 'Expiry:'), h('span', {}, o.expiry),
        h(NText, { depth: 3 }, () => 'Multiplier:'), h('span', {}, String(o.multiplier)),
        h(NText, { depth: 3 }, () => 'Style:'), h('span', {}, o.style),
      ],
    )
  }
  if (row.kind === 'forex' && row.forex) {
    const f = row.forex
    return h(
      'div',
      { style: 'display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; padding: 0.5rem 0;' },
      [
        h(NText, { depth: 3 }, () => 'Base:'), h('span', {}, f.base_currency),
        h(NText, { depth: 3 }, () => 'Quote:'), h('span', {}, f.quote_currency),
        h(NText, { depth: 3 }, () => 'Pip Size:'), h('span', {}, f.pip_size),
        h(NText, { depth: 3 }, () => 'Contract Size:'), h('span', {}, f.contract_size ?? '—'),
      ],
    )
  }
  return null
}
</script>

<template>
  <AuthenticatedLayout>
    <header class="instruments-header">
      <n-h1 style="margin: 0;">Instruments</n-h1>
      <n-button type="primary" @click="openCreate">+ New instrument</n-button>
    </header>

    <div class="filter-strip">
      <n-select
        v-model:value="kindFilter"
        :options="kindOptions"
        placeholder="Filter by kind"
        style="width: 160px;"
      />
      <n-input
        v-model:value="query"
        placeholder="Search by symbol"
        clearable
        style="max-width: 280px;"
      />
    </div>

    <n-alert v-if="error" type="error" :title="error" style="margin-bottom: 1rem;" />

    <n-data-table
      :columns="columns"
      :data="instruments"
      :loading="loading"
      :row-key="(row: Instrument) => row.id"
      :render-expand="renderExpand"
      size="small"
    >
      <template #empty>
        <n-empty description="No instruments yet — create one to get started.">
          <template #extra>
            <n-button type="primary" @click="openCreate">+ Create your first instrument</n-button>
          </template>
        </n-empty>
      </template>
    </n-data-table>

    <InstrumentForm v-model:show="modalShow" @saved="onSaved" />
  </AuthenticatedLayout>
</template>

<style scoped>
.instruments-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
  flex-wrap: wrap;
}
.filter-strip {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
</style>
