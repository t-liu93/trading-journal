import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsMcpView from '../src/views/SettingsMcpView.vue'
import { mcpTokensApi } from '../src/api/mcpTokens'

vi.mock('../src/api/mcpTokens', () => ({
  mcpTokensApi: { list: vi.fn(), create: vi.fn(), revoke: vi.fn() },
}))
vi.mock('naive-ui', () => ({
  useMessage: () => ({ success: vi.fn(), error: vi.fn() }),
}))
vi.mock('../src/components/AuthenticatedLayout.vue', () => ({
  default: defineComponent({ template: '<main><slot /></main>' }),
}))

const tokenRow = {
  id: 'mcp-id', name: 'Codex', profile: 'entry', token_prefix: 'tj_mcp_abc…',
  created_at: '2026-11-04T10:00:00Z', expires_at: '2027-02-02T10:00:00Z', revoked_at: null,
}

const stubs = {
  'n-space': defineComponent({ template: '<div><slot /></div>' }),
  'n-h1': defineComponent({ template: '<h1><slot /></h1>' }),
  'n-h3': defineComponent({ template: '<h3><slot /></h3>' }),
  'n-text': defineComponent({ template: '<span><slot /></span>' }),
  'n-button': defineComponent({ emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' }),
  'n-alert': defineComponent({ template: '<aside><slot /></aside>' }),
  'n-card': defineComponent({ template: '<section><slot /></section>' }),
  'n-form': defineComponent({ emits: ['submit'], template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>' }),
  'n-grid': defineComponent({ template: '<div><slot /></div>' }),
  'n-grid-item': defineComponent({ template: '<div><slot /></div>' }),
  'n-form-item': defineComponent({ template: '<label><slot /></label>' }),
  'n-input': defineComponent({ props: ['value'], emits: ['update:value'], template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />' }),
  'n-select': defineComponent({ props: ['value', 'options'], emits: ['update:value'], template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>' }),
  'n-spin': defineComponent({ template: '<div><slot /></div>' }),
  'n-empty': defineComponent({ template: '<p><slot /></p>' }),
  'n-table': defineComponent({ template: '<table><slot /></table>' }),
}

describe('SettingsMcpView', () => {
  beforeEach(() => {
    vi.mocked(mcpTokensApi.list).mockResolvedValue([tokenRow] as never)
    vi.mocked(mcpTokensApi.create).mockResolvedValue({ ...tokenRow, token: 'tj_mcp_secret-once' } as never)
    vi.mocked(mcpTokensApi.revoke).mockResolvedValue(null)
  })

  it('lists metadata, issues a credential once, and reveals it only in the current view', async () => {
    const wrapper = mount(SettingsMcpView, { global: { stubs } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('tj_mcp_abc'))
    expect(wrapper.text()).toContain('Codex')
    expect(wrapper.text()).toContain('entry')

    const input = wrapper.find('input')
    await input.setValue('New Codex')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(mcpTokensApi.create).toHaveBeenCalled())
    expect((wrapper.findAll('input').at(-1)!.element as HTMLInputElement).value).toBe('tj_mcp_secret-once')

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text() === 'Dismiss')!.trigger('click')
    expect(wrapper.findAll('input').some((field) => (field.element as HTMLInputElement).value === 'tj_mcp_secret-once')).toBe(false)
  })

  it('shows request errors and supports revocation', async () => {
    const wrapper = mount(SettingsMcpView, { global: { stubs } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('tj_mcp_abc'))
    await wrapper.findAll('button').find((button) => button.text() === 'Revoke')!.trigger('click')
    expect(mcpTokensApi.revoke).toHaveBeenCalledWith('mcp-id')

    vi.mocked(mcpTokensApi.list).mockRejectedValueOnce(new Error('network unavailable'))
    await wrapper.vm.$nextTick()
    await wrapper.unmount()
    const failing = mount(SettingsMcpView, { global: { stubs } })
    await vi.waitFor(() => expect(failing.text()).toContain('Could not load MCP credentials.'))
  })
})
