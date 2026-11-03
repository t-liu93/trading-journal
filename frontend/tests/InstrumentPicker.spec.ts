import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Instrument } from '../src/api/instruments'
import InstrumentPicker from '../src/components/InstrumentPicker.vue'

const { list } = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, list } }
})

vi.mock('naive-ui', () => ({ useMessage: () => ({ error: vi.fn(), success: vi.fn() }) }))

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
  props: ['value', 'options', 'loading', 'placeholder'],
  emits: ['focus', 'search', 'update:value'],
  setup(props, { emit }) {
    return () => h('div', { 'data-test': 'instrument-select', 'data-loading': String(props.loading) }, [
      h('button', { 'data-test': 'focus', onClick: () => emit('focus') }, 'Focus'),
      h('button', { 'data-test': 'search', onClick: () => emit('search', 'AAPL') }, 'Search AAPL'),
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

const InstrumentFormStub = defineComponent({
  props: ['show'],
  template: '<div data-test="instrument-form" />',
})

function mountPicker() {
  return mount(InstrumentPicker, {
    props: { modelValue: null, kind: 'stock' },
    global: {
      stubs: {
        NSelect: SelectStub,
        InstrumentForm: InstrumentFormStub,
      },
    },
  })
}

describe('InstrumentPicker', () => {
  beforeEach(() => {
    list.mockReset()
  })

  it('loads a search result and emits its ID and instrument when selected', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-03T12:00:00Z'))
    list.mockResolvedValueOnce([instrument])
    const wrapper = mountPicker()

    await wrapper.get('[data-test="search"]').trigger('click')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ q: 'AAPL', kind: 'stock' })
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
})
