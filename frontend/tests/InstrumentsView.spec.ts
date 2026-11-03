import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Instrument } from '../src/api/instruments'
import InstrumentsView from '../src/views/InstrumentsView.vue'

const { list } = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, list } }
})
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return { ...actual, NTag: 'span', NText: 'span' }
})

const rows: Instrument[] = Array.from({ length: 51 }, (_, index) => ({
  id: `stock-${index}`, kind: 'stock', symbol: `S${index}`, exchange: null, currency: 'USD',
  created_at: '2026-11-03T00:00:00Z', name: null, option: null,
}))
const button = defineComponent({
  props: ['disabled', 'loading'], emits: ['click'],
  setup(props, { emit, slots }) { return () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()) },
})
const dataTable = defineComponent({
  props: ['data'],
  template: '<div data-test="table"><span v-for="row in data" :key="row.id" data-test="row">{{ row.symbol }}</span><slot name="empty" /></div>',
})

describe('InstrumentsView', () => {
  beforeEach(() => { list.mockReset().mockResolvedValue(rows) })

  it('requests 51 rows and navigates by 50 while applying expiry visibility', async () => {
    vi.useFakeTimers()
    const wrapper = mount(InstrumentsView, { global: { stubs: {
      AuthenticatedLayout: { template: '<main><slot /></main>' },
      InstrumentForm: true,
      NButton: button,
      NAlert: defineComponent({ template: '<div role="alert"><slot /><span>{{ $attrs.title }}</span></div>' }),
      NSelect: defineComponent({ props: ['value', 'options'], emits: ['update:value'], template: '<select />' }),
      NInput: defineComponent({ props: ['value'], emits: ['update:value'], template: '<input />' }),
      NCheckbox: defineComponent({ props: ['checked'], emits: ['update:checked'], template: '<input type="checkbox" :checked="checked" @change="$emit(\'update:checked\', !$props.checked)" />' }),
      NCheckbox: defineComponent({ props: ['checked'], emits: ['update:checked'], template: '<input type="checkbox" :checked="checked" @change="$emit(\'update:checked\', !$props.checked)" />' }),
      NDataTable: dataTable,
      NEmpty: defineComponent({ template: '<div role="status"><slot /></div>' }), NH1: true,
    } } })
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(1, { kind: undefined, q: undefined, limit: 51, offset: 0, include_expired: false })
    await wrapper.get('[aria-label="Instrument pages"]').findAll('button').at(1)!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(2, { kind: undefined, q: undefined, limit: 51, offset: 50, include_expired: false })
    await wrapper.get('[aria-label="Instrument pages"]').findAll('button').at(0)!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(3, { kind: undefined, q: undefined, limit: 51, offset: 0, include_expired: false })
    await wrapper.get('[role="checkbox"]').trigger('click')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(list).toHaveBeenLastCalledWith({ kind: undefined, q: undefined, limit: 51, offset: 0, include_expired: true })
  })

  it('shows retryable errors without claiming the result set is empty', async () => {
    list.mockRejectedValueOnce(new Error('temporary outage')).mockResolvedValueOnce(rows)
    const wrapper = mount(InstrumentsView, { global: { stubs: {
      AuthenticatedLayout: { template: '<main><slot /></main>' }, InstrumentForm: true, NButton: button,
      NAlert: defineComponent({ template: '<div role="alert"><slot /><span>{{ $attrs.title }}</span></div>' }),
      NSelect: true, NInput: true, NCheckbox: true,
      NDataTable: dataTable,
      NEmpty: defineComponent({ template: '<div role="status" />' }), NH1: true,
    } } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Failed to load instruments.')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    await wrapper.findAll('button').find((item) => item.text() === 'Retry')!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('clears the old page after a failed Next and retries the target offset', async () => {
    const pageTwo = rows.map((row, index) => ({ ...row, id: `page-two-${index}`, symbol: `P2-${index}` }))
    list
      .mockResolvedValueOnce(rows)
      .mockRejectedValueOnce(new Error('page two unavailable'))
      .mockResolvedValueOnce(pageTwo)
    const wrapper = mount(InstrumentsView, { global: { stubs: {
      AuthenticatedLayout: { template: '<main><slot /></main>' }, InstrumentForm: true, NButton: button,
      NAlert: defineComponent({ template: '<div role="alert"><slot /><span>{{ $attrs.title }}</span></div>' }),
      NSelect: true, NInput: true, NCheckbox: true, NDataTable: dataTable,
      NEmpty: defineComponent({ template: '<div role="status" />' }), NH1: true,
    } } })
    await flushPromises()
    expect(wrapper.text()).toContain('S0')

    await wrapper.get('[aria-label="Instrument pages"]').findAll('button').at(1)!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(2, { kind: undefined, q: undefined, limit: 51, offset: 50, include_expired: false })
    expect(wrapper.findAll('[data-test="row"]')).toHaveLength(0)
    expect(wrapper.get('[role="alert"]').text()).toContain('Failed to load instruments.')
    expect(wrapper.text()).not.toContain('S0')

    await wrapper.findAll('button').find((item) => item.text() === 'Retry')!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(3, { kind: undefined, q: undefined, limit: 51, offset: 50, include_expired: false })
    expect(wrapper.text()).toContain('P2-0')
  })

  it('clears the old page after a failed Previous and retries offset zero', async () => {
    const pageTwo = rows.map((row, index) => ({ ...row, id: `page-two-${index}`, symbol: `P2-${index}` }))
    list
      .mockResolvedValueOnce(rows)
      .mockResolvedValueOnce(pageTwo)
      .mockRejectedValueOnce(new Error('first page unavailable'))
      .mockResolvedValueOnce(rows)
    const wrapper = mount(InstrumentsView, { global: { stubs: {
      AuthenticatedLayout: { template: '<main><slot /></main>' }, InstrumentForm: true, NButton: button,
      NAlert: defineComponent({ template: '<div role="alert"><slot /><span>{{ $attrs.title }}</span></div>' }),
      NSelect: true, NInput: true, NCheckbox: true, NDataTable: dataTable,
      NEmpty: defineComponent({ template: '<div role="status" />' }), NH1: true,
    } } })
    await flushPromises()
    await wrapper.get('[aria-label="Instrument pages"]').findAll('button').at(1)!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('P2-0')

    await wrapper.get('[aria-label="Instrument pages"]').findAll('button').at(0)!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(3, { kind: undefined, q: undefined, limit: 51, offset: 0, include_expired: false })
    expect(wrapper.findAll('[data-test="row"]')).toHaveLength(0)
    expect(wrapper.get('[role="alert"]').text()).toContain('Failed to load instruments.')
    expect(wrapper.text()).not.toContain('P2-0')

    await wrapper.findAll('button').find((item) => item.text() === 'Retry')!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(4, { kind: undefined, q: undefined, limit: 51, offset: 0, include_expired: false })
    expect(wrapper.text()).toContain('S0')
  })
})
