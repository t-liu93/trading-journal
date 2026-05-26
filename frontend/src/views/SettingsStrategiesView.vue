<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { type DataTableColumns, type FormInst, type FormRules, NButton, NSpace, NTag, useMessage } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import CurrencySelect from '../components/CurrencySelect.vue'
import { useStrategyConfigs } from '../composables/useStrategyConfigs'
import {
  type StrategyConfig,
  type StrategyType,
  type StrategyConfigCreate,
  type StrategyConfigUpdate,
  strategyConfigsApi,
} from '../api/strategyConfigs'
import { ApiError } from '../api/types'

const { configs, loading, error, refresh } = useStrategyConfigs()
const message = useMessage()

onMounted(refresh)

const strategyLabels = {
  wheel: 'Wheel',
  iron_condor: 'Iron Condor',
  pmcc: 'PMCC / LEAP',
  spot_stock: 'Spot Stock',
  spot_forex: 'Spot Forex',
} satisfies Record<StrategyType, string>

const allStrategyTypes = Object.keys(strategyLabels) as StrategyType[]

interface RowData {
  strategy_type: StrategyType
  label: string
  config: StrategyConfig | null
}

const rows = computed<RowData[]>(() =>
  allStrategyTypes.map((t) => ({
    strategy_type: t,
    label: strategyLabels[t],
    config: configs.value.find((c) => c.strategy_type === t) ?? null,
  })),
)

const dateFmt = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Backend stores UTC but SQLite returns naive datetimes (no "Z" suffix).
 *  Append Z so JS parses as UTC, then Intl.DateTimeFormat converts to local. */
function parseUtc(iso: string): Date {
  return new Date(iso.endsWith('Z') ? iso : iso + 'Z')
}

// --- Edit modal ---
const modalShow = ref(false)
const editingType = ref<StrategyType | null>(null)
const editingExisting = ref(false)
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)

interface FormModel {
  max_exposure: number | null
  exposure_currency: string | null
  notes: string
}
const formModel = ref<FormModel>({ max_exposure: null, exposure_currency: null, notes: '' })

const formRules: FormRules = {
  max_exposure: [
    {
      validator: (_rule, value) => {
        if (value != null && (!Number.isFinite(value) || value <= 0)) {
          return new Error('Must be greater than 0, or leave empty for no cap')
        }
        return true
      },
    },
  ],
  exposure_currency: [
    { required: true, message: 'Currency is required' },
    {
      validator: (_rule, value) => {
        if (value && !/^[A-Z]{3}$/.test(value)) {
          return new Error('Must be a 3-letter currency code (e.g. USD)')
        }
        return true
      },
    },
  ],
}

function openEdit(row: RowData) {
  editingType.value = row.strategy_type
  editingExisting.value = row.config !== null
  if (row.config) {
    formModel.value = {
      max_exposure: row.config.max_exposure != null ? Number(row.config.max_exposure) : null,
      exposure_currency: row.config.exposure_currency,
      notes: row.config.notes ?? '',
    }
  } else {
    formModel.value = { max_exposure: null, exposure_currency: null, notes: '' }
  }
  modalShow.value = true
}

function handleClose() {
  modalShow.value = false
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const notes = formModel.value.notes || null
    const maxExposure = formModel.value.max_exposure

    if (editingExisting.value) {
      // PATCH — update existing config
      const patchPayload: StrategyConfigUpdate = {
        max_exposure: maxExposure,
        exposure_currency: formModel.value.exposure_currency,
        notes,
      }
      await strategyConfigsApi.update(editingType.value!, patchPayload)
    } else {
      // POST — create new config
      const postPayload: StrategyConfigCreate = {
        strategy_type: editingType.value!,
        exposure_currency: formModel.value.exposure_currency!,
        max_exposure: maxExposure,
        notes,
      }
      await strategyConfigsApi.upsert(postPayload)
    }

    await refresh()
    message.success(`${strategyLabels[editingType.value!]} config saved`)
    handleClose()
  } catch (err) {
    if (err instanceof ApiError) {
      message.error(err.message)
    } else {
      throw err
    }
  } finally {
    submitting.value = false
  }
}

const columns = computed<DataTableColumns<RowData>>(() => [
  {
    title: 'Strategy',
    key: 'label',
    render: (row) => h(NTag, { size: 'small' }, () => row.label),
  },
  {
    title: 'Max Exposure',
    key: 'max_exposure',
    render: (row) => row.config?.max_exposure ?? '—',
  },
  {
    title: 'Currency',
    key: 'exposure_currency',
    render: (row) => row.config?.exposure_currency ?? '—',
  },
  {
    title: 'Notes',
    key: 'notes',
    ellipsis: { tooltip: true },
    render: (row) => row.config?.notes ?? '',
  },
  {
    title: 'Updated',
    key: 'updated_at',
    render: (row) => (row.config ? dateFmt.format(parseUtc(row.config.updated_at)) : '—'),
  },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h(
        NSpace,
        { size: 'small' },
        () => [
          h(
            NButton,
            { text: true, type: 'primary', size: 'small', onClick: () => openEdit(row) },
            () => row.config ? 'Edit' : 'Set up',
          ),
        ],
      ),
  },
])
</script>

<template>
  <AuthenticatedLayout>
    <header class="strategies-header">
      <n-h1 style="margin: 0;">Strategy Exposure Caps</n-h1>
    </header>
    <n-text depth="3" style="display: block; margin-bottom: 1.5rem;">
      Set a maximum aggregate max_risk_at_open per strategy. Manual for MVP — broker API
      integration will enforce these caps at order time.
    </n-text>

    <n-alert v-if="error" type="error" :title="error" style="margin-bottom: 1rem;" />

    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :row-key="(row: RowData) => row.strategy_type"
      size="small"
    />

    <n-modal
      :show="modalShow"
      :title="editingType ? `Edit ${strategyLabels[editingType]} cap` : 'Edit cap'"
      preset="card"
      style="max-width: 480px;"
      :mask-closable="!submitting"
      @update:show="modalShow = $event"
    >
      <n-form ref="formRef" :model="formModel" :rules="formRules" label-placement="top">
        <n-form-item label="Max Exposure" path="max_exposure">
          <n-input-number
            v-model:value="formModel.max_exposure"
            placeholder="Leave empty for no cap"
            style="width: 100%;"
            :disabled="submitting"
            clearable
          />
        </n-form-item>
        <n-form-item label="Exposure Currency" path="exposure_currency">
          <CurrencySelect v-model:model-value="formModel.exposure_currency" :disabled="submitting" />
        </n-form-item>
        <n-form-item label="Notes" path="notes">
          <n-input
            v-model:value="formModel.notes"
            type="textarea"
            placeholder="Optional notes"
            :disabled="submitting"
          />
        </n-form-item>
      </n-form>

      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <n-button @click="handleClose" :disabled="submitting">Cancel</n-button>
          <n-button type="primary" @click="handleSubmit" :loading="submitting">Save</n-button>
        </div>
      </template>
    </n-modal>
  </AuthenticatedLayout>
</template>

<style scoped>
.strategies-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
</style>
