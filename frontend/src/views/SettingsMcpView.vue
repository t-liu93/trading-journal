<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useMessage } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import { type McpToken, mcpTokensApi } from '../api/mcpTokens'
import { ApiError } from '../api/types'

const message = useMessage()
const tokens = ref<McpToken[]>([])
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const name = ref('')
const profile = ref<'read' | 'entry'>('read')
const expiry = ref<'90' | 'custom' | 'never'>('90')
const customExpiry = ref<number | null>(null)
const revealedToken = ref('')
const revealedName = ref('')
const revealVisible = ref(false)

function clearReveal() {
  revealedToken.value = ''
  revealedName.value = ''
  revealVisible.value = false
}

onBeforeUnmount(clearReveal)

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    tokens.value = await mcpTokensApi.list()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not load MCP credentials.'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

async function issue() {
  if (!name.value.trim()) {
    error.value = 'Enter a name for this credential.'
    return
  }
  if (expiry.value === 'custom' && customExpiry.value === null) {
    error.value = 'Choose a future expiry date and time.'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const issued = await mcpTokensApi.create({
      name: name.value.trim(),
      profile: profile.value,
      ...(expiry.value === 'never'
        ? { expires_at: null }
        : expiry.value === 'custom' && customExpiry.value !== null
          ? { expires_at: new Date(customExpiry.value).toISOString() }
          : {}),
    })
    revealedToken.value = issued.token
    revealedName.value = issued.name
    revealVisible.value = true
    name.value = ''
    await refresh()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not create MCP credential.'
  } finally {
    submitting.value = false
  }
}

async function revoke(token: McpToken) {
  error.value = ''
  try {
    await mcpTokensApi.revoke(token.id)
    message.success(`${token.name} revoked`)
    await refresh()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'Could not revoke MCP credential.'
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(revealedToken.value)
    message.success('Credential copied. Store it in a password manager or client environment.')
  } catch {
    error.value = 'Clipboard access failed. Select and copy the revealed credential manually.'
  }
}

function formatDate(value: string | null) {
  if (!value) return 'Never'
  const utc = value.endsWith('Z') ? value : `${value}Z`
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(utc))
}
</script>

<template>
  <AuthenticatedLayout>
    <n-space vertical size="large" class="settings-page">
      <div>
        <n-h1 style="margin: 0 0 8px">MCP credentials</n-h1>
        <n-text depth="3">Issue separate credentials for each agent. The secret is shown once and is never stored in this browser.</n-text>
        <n-space style="margin-top: 12px">
          <n-button secondary tag="a" href="/settings/strategies">Strategy settings</n-button>
        </n-space>
      </div>

      <n-alert v-if="error" type="error" closable @close="error = ''">{{ error }}</n-alert>

      <n-card title="Create credential">
        <n-form @submit.prevent="issue">
          <n-grid :cols="1" :x-gap="16" :y-gap="8" responsive="screen" :item-responsive="true">
            <n-grid-item span="1 m:8"><n-form-item label="Name"><n-input v-model:value="name" placeholder="Codex laptop" /></n-form-item></n-grid-item>
            <n-grid-item span="1 m:4"><n-form-item label="Permission"><n-select v-model:value="profile" :options="[{ label: 'Read only', value: 'read' }, { label: 'Entry: read and prepare/commit', value: 'entry' }]" /></n-form-item></n-grid-item>
            <n-grid-item span="1 m:4"><n-form-item label="Expiry"><n-select v-model:value="expiry" :options="[{ label: '90 days (default)', value: '90' }, { label: 'Choose date', value: 'custom' }, { label: 'Never', value: 'never' }]" /></n-form-item></n-grid-item>
            <n-grid-item v-if="expiry === 'custom'" span="1 m:4"><n-form-item label="Expires at"><n-date-picker v-model:value="customExpiry" type="datetime" clearable /></n-form-item></n-grid-item>
          </n-grid>
          <n-button type="primary" attr-type="submit" :loading="submitting">Create credential</n-button>
        </n-form>
      </n-card>

      <n-alert v-if="revealVisible" type="warning" title="Copy this credential now">
        <p>{{ revealedName }} is shown only this time. Dismiss this panel or leave this page to clear it.</p>
        <n-input :value="revealedToken" readonly type="password" show-password-on="click" />
        <n-space style="margin-top: 12px">
          <n-button type="primary" @click="copyToken">Copy credential</n-button>
          <n-button @click="clearReveal">Dismiss</n-button>
        </n-space>
      </n-alert>

      <n-card title="Credentials">
        <n-spin :show="loading">
          <n-empty v-if="!loading && tokens.length === 0" description="No MCP credentials yet" />
          <n-table v-else :bordered="false" :single-line="false">
            <thead><tr><th>Name</th><th>Permission</th><th>Prefix</th><th>Created</th><th>Expires</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="token in tokens" :key="token.id">
                <td>{{ token.name }}</td><td>{{ token.profile }}</td><td><code>{{ token.token_prefix }}…</code></td>
                <td>{{ formatDate(token.created_at) }}</td><td>{{ formatDate(token.expires_at) }}</td>
                <td>{{ token.revoked_at ? `Revoked ${formatDate(token.revoked_at)}` : 'Active' }}</td>
                <td><n-button v-if="!token.revoked_at" size="small" type="error" secondary @click="revoke(token)">Revoke</n-button></td>
              </tr>
            </tbody>
          </n-table>
        </n-spin>
      </n-card>

      <n-card title="Connect an agent">
        <n-text depth="3">Use a different credential for each client. Replace the placeholder locally; do not paste credentials into shared documents or chats.</n-text>
        <n-h3>Codex CLI</n-h3>
        <pre><code>export JOURNAL_MCP_TOKEN='paste-your-credential-here'
codex mcp add trading-journal --url http://localhost:8000/api/mcp --bearer-token-env-var JOURNAL_MCP_TOKEN</code></pre>
        <n-h3>Hermes Agent</n-h3>
        <pre v-pre><code># Put JOURNAL_MCP_TOKEN in the environment or Hermes .env file
mcp_servers:
  trading-journal:
    url: "http://localhost:8000/api/mcp"
    headers:
      Authorization: "Bearer ${JOURNAL_MCP_TOKEN}"</code></pre>
        <n-text depth="3">Hermes expands environment variable references in MCP configuration before sending headers. These examples configure clients; they do not verify a live client connection.</n-text>
      </n-card>
    </n-space>
  </AuthenticatedLayout>
</template>

<style scoped>
.settings-page { max-width: 1100px; margin: 0 auto; }
pre { overflow-x: auto; padding: 14px; border-radius: 6px; background: var(--n-code-color); }
</style>
