import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NSelect } from 'naive-ui'
import type { Instrument } from '../src/api/instruments'
import InstrumentPicker from '../src/components/InstrumentPicker.vue'

const { list, get } = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn() }))

vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, list, get } }
})

const { messageInfo } = vi.hoisted(() => ({ messageInfo: vi.fn() }))
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return { ...actual, useMessage: () => ({ error: vi.fn(), success: vi.fn(), info: messageInfo }) }
})

const instrument: Instrument = {
  id: 'stock-aapl',
  kind: 'stock',
  symbol: 'AAPL',
  exchange: 'NASDAQ',
  currency: 'USD',
  name: 'Apple Inc.',
  option: null,
}

const SelectStub = defineComponent({
  props: ['value', 'options', 'loading', 'placeholder', 'fallbackOption'],
  emits: ['focus', 'search', 'update:value', 'update:show'],
  setup(props, { emit, slots }) {
    return () => h('div', { 'data-test': 'instrument-select', 'data-loading': String(props.loading) }, [
      h('span', { 'data-test': 'selected-label' }, props.value && props.fallbackOption ? props.fallbackOption(props.value).label : ''),
      h('button', { 'data-test': 'focus', onClick: () => emit('focus') }, 'Focus'),
      h('button', { 'data-test': 'open', onClick: () => emit('update:show', true) }, 'Open'),
      h('button', { 'data-test': 'close', onClick: () => emit('update:show', false) }, 'Close'),
      h('button', { 'data-test': 'search', onClick: () => emit('search', 'AAPL') }, 'Search AAPL'),
      slots.action?.(),
      ...(props.options as Array<{ label: string; value: string }>).map((option) =>
        h('button', {
          key: option.value,
          'data-test': `option-${option.value}`,
          onClick: () => emit('update:value', option.value),
        }, option.label),
      ),
    ])
  },
})

const realSelectShowEvents: boolean[] = []
const ObservedRealSelect = defineComponent({
  inheritAttrs: false,
  emits: ['update:show'],
  setup(_, { attrs, emit, slots }) {
    return () => h(NSelect, {
      ...attrs,
      onUpdateShow: (show: boolean) => {
        realSelectShowEvents.push(show)
        emit('update:show', show)
      },
    }, slots)
  },
})

const InstrumentFormStub = defineComponent({
  props: ['show'],
  emits: ['saved'],
  template: '<div data-test="instrument-form" />',
})

function mountPicker() {
  return mount(InstrumentPicker, {
    props: { modelValue: null, kind: 'stock' },
    global: {
      stubs: {
        NSelect: SelectStub,
        NButton: defineComponent({ emits: ['click'], setup(_, { emit, slots }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) } }),
        NCheckbox: defineComponent({
          props: ['checked'], emits: ['update:checked'],
          setup(props, { emit }) { return () => h('label', [h('input', { type: 'checkbox', checked: props.checked, onChange: () => emit('update:checked', !props.checked) }), ' Show expired options']) },
        }),
        InstrumentForm: InstrumentFormStub,
      },
    },
  })
}

describe('InstrumentPicker', () => {
  beforeEach(() => {
    list.mockReset()
    get.mockReset()
    messageInfo.mockReset()
    realSelectShowEvents.length = 0
  })

  it('loads a search result and emits its ID and instrument when selected', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-03T12:00:00Z'))
    list.mockResolvedValueOnce([instrument])
    const wrapper = mountPicker()

    await wrapper.get('[data-test="search"]').trigger('click')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ q: 'AAPL', kind: 'stock', limit: 51, offset: 0, include_expired: false })
    expect(wrapper.get('[data-test="option-stock-aapl"]').text()).toBe('AAPL (NASDAQ) [stock]')

    await wrapper.get('[data-test="option-stock-aapl"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['stock-aapl']])
    expect(wrapper.emitted('update:instrument')).toEqual([[instrument]])
  })

  it('ignores an older search response after a newer request completes', async () => {
    vi.useFakeTimers()
    let resolveOld: ((items: Instrument[]) => void) | undefined
    list
      .mockImplementationOnce(() => new Promise<Instrument[]>((resolve) => { resolveOld = resolve }))
      .mockResolvedValueOnce([instrument])
    const wrapper = mountPicker()

    await wrapper.get('[data-test="focus"]').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-test="search"]').trigger('click')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-test="option-stock-aapl"]').exists()).toBe(true)

    resolveOld?.([])
    await flushPromises()

    expect(wrapper.get('[data-test="option-stock-aapl"]').exists()).toBe(true)
  })

  it('cancels an older pending debounce when search context changes', async () => {
    vi.useFakeTimers()
    list.mockResolvedValue([instrument])
    const wrapper = mountPicker()
    const select = wrapper.findComponent(SelectStub)
    await select.vm.$emit('search', 'OLD')
    await select.vm.$emit('search', 'NEW')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(1)
    expect(list).toHaveBeenCalledWith({ q: 'NEW', kind: 'stock', limit: 51, offset: 0, include_expired: false, option_underlying_id: undefined })
  })

  it('reloads when the dropdown is reopened without another focus event', async () => {
    list.mockResolvedValue([])
    const wrapper = mountPicker()
    await wrapper.get('[data-test="open"]').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-test="close"]').trigger('click')
    await wrapper.get('[data-test="open"]').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('requests 51 rows, appends by ID, and retries a failed second page at the same offset', async () => {
    vi.useFakeTimers()
    const rows = Array.from({ length: 51 }, (_, index) => ({ ...instrument, id: `stock-${index}`, symbol: `S${index}` }))
    list.mockResolvedValueOnce(rows).mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce([rows[50]])
    const wrapper = mountPicker()

    await wrapper.get('[data-test="focus"]').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(1, { q: undefined, kind: 'stock', limit: 51, offset: 0, include_expired: false })

    // The test control exposes the component's rendered append/retry actions.
    await wrapper.get('[data-test="instrument-select"]').trigger('click')
    await flushPromises()
    const loadMore = wrapper.findAll('button').find((button) => button.text() === 'Load more')
    expect(loadMore).toBeDefined()
    await loadMore!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(2, { q: undefined, kind: 'stock', limit: 51, offset: 50, include_expired: false })
    expect(wrapper.get('[role="alert"]').text()).toContain('network')

    const retry = wrapper.findAll('button').find((button) => button.text() === 'Retry')
    await retry!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenNthCalledWith(3, { q: undefined, kind: 'stock', limit: 51, offset: 50, include_expired: false })
    expect(wrapper.get('[data-test="option-stock-50"]').exists()).toBe(true)
  })

  it('keeps an off-page selected value as a label only and exposes expired candidates only when enabled', async () => {
    const historical: Instrument = { ...instrument, id: 'historical-option', kind: 'option', symbol: 'AAPL', option: {
      underlying_id: 'stock-aapl', opt_type: 'call', strike: '200', expiry: '2026-11-02', multiplier: 100, style: 'american',
    } }
    get.mockResolvedValue(historical)
    list.mockResolvedValue([instrument])
    const wrapper = mount(InstrumentPicker, {
      props: { modelValue: historical.id, kind: 'option', optionUnderlyingId: 'stock-aapl' },
      global: { stubs: {
        NSelect: SelectStub,
        NButton: defineComponent({ emits: ['click'], setup(_, { emit, slots }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) } }),
        NCheckbox: defineComponent({ props: ['checked'], emits: ['update:checked'], template: '<input type="checkbox" :checked="checked" @change="$emit(\'update:checked\', !$props.checked)" />' }),
        InstrumentForm: InstrumentFormStub,
      } },
    })
    await flushPromises()
    expect(get).toHaveBeenCalledWith(historical.id)
    await wrapper.get('[data-test="focus"]').trigger('click')
    await flushPromises()
    const select = wrapper.get('[data-test="instrument-select"]')
    expect(select.find('[data-test="option-historical-option"]').exists()).toBe(false)
    expect(select.get('[data-test="selected-label"]').text()).not.toContain('historical-option')
    expect(select.get('[data-test="selected-label"]').text()).toContain('AAPL')
    expect(list).toHaveBeenLastCalledWith({ q: undefined, kind: 'option', limit: 51, offset: 0, include_expired: false, option_underlying_id: 'stock-aapl' })
    await wrapper.get('[role="checkbox"]').trigger('click')
    await flushPromises()
    expect(list).toHaveBeenLastCalledWith({ q: undefined, kind: 'option', limit: 51, offset: 0, include_expired: true, option_underlying_id: 'stock-aapl' })
  })

  it('enables and explains historical access when a newly created option is expired', async () => {
    const historical: Instrument = { ...instrument, id: 'historical-option', kind: 'option', symbol: 'AAPL', option: {
      underlying_id: 'stock-aapl', opt_type: 'call', strike: '200', expiry: '2026-11-02', multiplier: 100, style: 'american',
    } }
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-03T12:00:00Z'))
    list.mockResolvedValue([])
    const wrapper = mount(InstrumentPicker, {
      props: { modelValue: null, kind: 'option', allowCreate: true, optionUnderlyingId: 'stock-aapl' },
      global: { stubs: { NSelect: SelectStub, NButton: true, NCheckbox: true, InstrumentForm: InstrumentFormStub } },
    })
    await wrapper.findComponent(InstrumentFormStub).vm.$emit('saved', historical)
    await nextTick()
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')).toEqual([[historical.id]])
    expect(messageInfo).toHaveBeenCalledWith(expect.stringContaining('Expired options are now shown'))
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ include_expired: true }))
  })

  it('keeps the real Select open when paging and retrying from its action slot', async () => {
    const rows = Array.from({ length: 51 }, (_, index) => ({ ...instrument, id: `stock-${index}`, symbol: `S${index}` }))
    list.mockResolvedValueOnce(rows).mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce([rows[50]]).mockResolvedValueOnce([rows[0]])
    const wrapper = mount(InstrumentPicker, {
      props: { modelValue: null, kind: 'stock' },
      attachTo: document.body,
      global: { components: { 'n-select': ObservedRealSelect }, stubs: { InstrumentForm: InstrumentFormStub } },
    })
    try {
      const selection = wrapper.get('.n-base-selection-label')
      await selection.trigger('click')
      await flushPromises()
      expect(list).toHaveBeenCalledTimes(1)
      expect(realSelectShowEvents).toEqual([true])

      const loadMore = Array.from(document.body.querySelectorAll('button')).find((button) => button.textContent?.includes('Load more'))
      expect(loadMore).toBeDefined()
      loadMore!.click()
      await flushPromises()
      expect(list).toHaveBeenNthCalledWith(2, { q: undefined, kind: 'stock', limit: 51, offset: 50, include_expired: false, option_underlying_id: undefined })
      expect(document.body.querySelector('[role="alert"]')?.textContent).toContain('network')
      expect(realSelectShowEvents).toEqual([true])

      const retry = Array.from(document.body.querySelectorAll('button')).find((button) => button.textContent?.includes('Retry'))
      expect(retry).toBeDefined()
      retry!.click()
      await flushPromises()
      expect(list).toHaveBeenNthCalledWith(3, { q: undefined, kind: 'stock', limit: 51, offset: 50, include_expired: false, option_underlying_id: undefined })
      expect(wrapper.getComponent(NSelect).props('options')).toContainEqual({ label: 'S50 (NASDAQ) [stock]', value: 'stock-50' })
      expect(realSelectShowEvents).toEqual([true])

      document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
      document.body.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
      await flushPromises()
      expect(realSelectShowEvents).toEqual([true, false])
      await wrapper.get('.n-base-selection-label').trigger('click')
      await flushPromises()
      expect(realSelectShowEvents).toEqual([true, false, true])
      expect(list).toHaveBeenCalledTimes(4)
      expect(list).toHaveBeenNthCalledWith(4, { q: undefined, kind: 'stock', limit: 51, offset: 0, include_expired: false, option_underlying_id: undefined })
      expect(wrapper.getComponent(NSelect).props('options')).toContainEqual({ label: 'S0 (NASDAQ) [stock]', value: 'stock-0' })
    } finally {
      wrapper.unmount()
    }
  })
})
