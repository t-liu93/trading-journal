<script setup lang="ts">
import { computed, h, onMounted } from 'vue'
import { type DataTableColumns, NTag, NText } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import { useAccounts } from '../composables/useAccounts'
import type { Account } from '../api/accounts'

const { accounts, loading, error, includeArchived, refresh } = useAccounts()

onMounted(refresh)

function isArchived(row: Account): boolean {
  return row.archived_at !== null
}

const dateFmt = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
})

const columns = computed<DataTableColumns<Account>>(() => [
  {
    title: 'Name',
    key: 'name',
    render: (row) => {
      if (!isArchived(row)) return row.name
      return h('span', {}, [
        row.name,
        h(
          NTag,
          { size: 'small', type: 'default', style: 'margin-left: 0.5rem;' },
          { default: () => 'archived' },
        ),
      ])
    },
  },
  { title: 'Broker', key: 'broker' },
  { title: 'Type', key: 'account_type' },
  { title: 'Currency', key: 'base_currency' },
  {
    title: 'Notes',
    key: 'notes',
    ellipsis: { tooltip: true },
    render: (row) => row.notes ?? '',
  },
  {
    title: 'Created',
    key: 'created_at',
    render: (row) => dateFmt.format(new Date(row.created_at)),
  },
  {
    title: 'Actions',
    key: 'actions',
    render: () => h(NText, { depth: 3 }, () => '(F1.4 / F1.5)'),
  },
])

// Visually demote archived rows so the toggle-on state is readable.
function rowClassName(row: Account): string {
  return isArchived(row) ? 'archived-row' : ''
}
</script>

<template>
  <AuthenticatedLayout>
    <header class="accounts-header">
      <n-h1 style="margin: 0;">Accounts</n-h1>
      <div class="accounts-controls">
        <div class="archived-toggle">
          <n-switch v-model:value="includeArchived" size="small" />
          <n-text depth="2">Show archived</n-text>
        </div>
        <n-button type="primary" disabled>+ New account</n-button>
      </div>
    </header>

    <n-alert v-if="error" type="error" :title="error" style="margin-bottom: 1rem;" />

    <n-data-table
      :columns="columns"
      :data="accounts"
      :loading="loading"
      :row-key="(row: Account) => row.id"
      :row-class-name="rowClassName"
      size="small"
    >
      <template #empty>
        <n-empty description="No accounts yet.">
          <template #extra>
            <n-button type="primary" disabled>+ Create your first account</n-button>
          </template>
        </n-empty>
      </template>
    </n-data-table>
  </AuthenticatedLayout>
</template>

<style scoped>
.accounts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}
.accounts-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.archived-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>

<style>
/* Global because n-data-table renders rows outside this component's scope. */
.archived-row td {
  opacity: 0.55;
}
</style>
