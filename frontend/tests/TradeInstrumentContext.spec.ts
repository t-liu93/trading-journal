import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Instrument } from '../src/api/instruments'
import InstrumentPicker from '../src/components/InstrumentPicker.vue'
import TradeLegRow from '../src/components/TradeLegRow.vue'
import { getOptionUnderlyingId } from '../src/utils/instrumentContext'

const { list, get, warning } = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), warning: vi.fn() }))
vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, list, get } }
})
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return { ...actual, useMessage: () => ({ error: vi.fn(), warning, info: vi.fn() }) }
})

const stockA: Instrument = { id: 'stock-a', kind: 'stock', symbol: 'DUP', exchange: 'X', currency: 'USD', created_at: '', option: null }
const stockB: Instrument = { ...stockA, id: 'stock-b' }
const optionA: Instrument = { ...stockA, id: 'option-a', kind: 'option', option: {
  underlying_id: stockA.id, opt_type: 'call', strike: '100', expiry: '2027-01-15', multiplier: 100, style: 'american',
} }
const optionB: Instrument = { ...optionA, id: 'option-b', option: { ...optionA.option!, underlying_id: stockB.id } }

const SelectStub = defineComponent({
  props: ['value', 'options', 'loading', 'fallbackOption'],
  emits: ['focus', 'update:value', 'update:show', 'search'],
  setup(props, { emit, slots }) {
    return () => h('div', [
      h('button', { 'data-test': 'open', onClick: () => emit('focus') }, 'open'),
      h('button', { 'data-test': 'show', onClick: () => emit('update:show', true) }, 'show'),
      ...(props.options as Array<{ label: string; value: string }>).map(option => h('button', {
        key: option.value, 'data-test': `pick-${option.value}`, onClick: () => emit('update:value', option.value),
      }, option.label)),
      slots.action?.(),
    ])
  },
})
const StubButton = defineComponent({ emits: ['click'], setup(_, { emit, slots }) { return () => h('button', { onClick: () => emit('click') }, slots.default?.()) } })
const CheckboxStub = defineComponent({ props: ['checked'], emits: ['update:checked'], template: '<span />' })
const FormStub = defineComponent({ props: ['show'], emits: ['saved'], template: '<div />' })
const NumberStub = defineComponent({ props: ['value'], emits: ['update:value'], template: '<input type="number" />' })
const TextareaStub = defineComponent({
  props: ['modelValue'], emits: ['update:modelValue'],
  setup(props, { emit }) { return () => h('textarea', { 'data-test': 'notes', value: props.modelValue, onInput: (event: Event) => emit('update:modelValue', (event.target as HTMLTextAreaElement).value) }) },
})
const pickerStubs = { NSelect: SelectStub, NButton: StubButton, NCheckbox: CheckboxStub, InstrumentForm: FormStub }

describe('exact primary instrument context', () => {
  beforeEach(() => { list.mockReset(); get.mockReset(); warning.mockReset() })

  it('resolves stock and option primaries by underlying ID, never by symbol', () => {
    expect(getOptionUnderlyingId(stockA)).toBe('stock-a')
    expect(getOptionUnderlyingId(optionB)).toBe('stock-b')
    expect(getOptionUnderlyingId({ ...stockA, kind: 'forex', forex: null })).toBeNull()
    expect(getOptionUnderlyingId(null)).toBeNull()
  })

  it('sends the exact underlying query and filters a same-symbol wrong-ID response', async () => {
    list.mockResolvedValue([optionA, optionB])
    get.mockResolvedValue(optionA)
    const wrapper = mount(InstrumentPicker, { props: {
      modelValue: optionA.id, kind: 'option', optionUnderlyingId: stockA.id,
    }, global: { stubs: pickerStubs } })
    await wrapper.get('[data-test="open"]').trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ kind: 'option', option_underlying_id: 'stock-a' }))
    expect(wrapper.find('[data-test="pick-option-a"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pick-option-b"]').exists()).toBe(false)
  })

  it('limits all related candidates to the exact stock ID and its options', async () => {
    const forex: Instrument = { ...stockA, id: 'forex-a', kind: 'forex', forex: null }
    list.mockResolvedValue([stockA, stockB, optionA, optionB, forex])
    get.mockResolvedValue(stockA)
    const wrapper = mount(InstrumentPicker, { props: {
      modelValue: null, relatedUnderlyingId: stockA.id, searchContextKey: stockA.id,
    }, global: { stubs: pickerStubs } })
    await wrapper.get('[data-test="open"]').trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ related_underlying_id: stockA.id }))
    expect(wrapper.find('[data-test="pick-stock-a"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pick-option-a"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pick-stock-b"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="pick-option-b"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="pick-forex-a"]').exists()).toBe(false)
  })

  it('cancels pending A search and ignores its late response after switching to B', async () => {
    vi.useFakeTimers()
    let resolveA: ((rows: Instrument[]) => void) | undefined
    list.mockImplementationOnce(() => new Promise<Instrument[]>((resolve) => { resolveA = resolve }))
      .mockResolvedValue([stockB, optionB])
    const wrapper = mount(InstrumentPicker, { props: {
      modelValue: null, relatedUnderlyingId: stockA.id, searchContextKey: stockA.id,
    }, global: { stubs: pickerStubs } })
    const select = wrapper.findComponent(SelectStub)
    await select.vm.$emit('update:show', true)
    await flushPromises()
    await select.vm.$emit('search', 'AAA')
    await wrapper.setProps({ relatedUnderlyingId: stockB.id, searchContextKey: stockB.id })
    await vi.advanceTimersByTimeAsync(350)
    await flushPromises()
    resolveA?.([stockA, optionA])
    await flushPromises()

    expect(list.mock.calls.slice(1).every(([params]) => params.related_underlying_id === stockB.id && params.q === undefined)).toBe(true)
    expect(wrapper.find('[data-test="pick-stock-b"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pick-option-b"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pick-option-a"]').exists()).toBe(false)
  })

  it('does not select an inline-created instrument outside the current relation', async () => {
    const wrapper = mount(InstrumentPicker, { props: {
      modelValue: null, allowCreate: true, relatedUnderlyingId: stockA.id,
    }, global: { stubs: pickerStubs } })
    await wrapper.findComponent(FormStub).vm.$emit('saved', optionB)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.emitted('update:instrument')).toBeUndefined()
  })

  it('clears a selected option when resolved primary changes to a different same-symbol stock', async () => {
    get.mockImplementation(async (id: string) => id === optionA.id ? optionA : id === stockB.id ? stockB : stockA)
    list.mockResolvedValue([optionA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA, primaryInstrumentLoading: false,
    }, global: { stubs: { ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' }, NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button', NSelect: true, NInputNumber: true, NDatePicker: true, NInput: true } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', optionA.id)
    await picker.vm.$emit('update:instrument', optionA)
    await flushPromises()
    expect(picker.props('modelValue')).toBe(optionA.id)

    await wrapper.setProps({ primaryInstrument: stockB })
    await flushPromises()
    expect(picker.props('modelValue')).toBeNull()
  })

  it('keeps the option selection when a different primary instrument resolves to the same underlying ID', async () => {
    const optionPrimary: Instrument = { ...optionA, id: 'primary-option', option: { ...optionA.option!, underlying_id: stockA.id } }
    get.mockImplementation(async (id: string) => id === optionA.id ? optionA : optionPrimary)
    list.mockResolvedValue([optionA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA, primaryInstrumentLoading: false,
    }, global: { stubs: { ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' }, NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button', NSelect: true, NInputNumber: true, NDatePicker: true, NInput: true } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', optionA.id)
    await picker.vm.$emit('update:instrument', optionA)
    await flushPromises()
    await wrapper.setProps({ primaryInstrument: optionPrimary })
    await flushPromises()
    expect(picker.props('modelValue')).toBe(optionA.id)
  })

  it('clears and explains a selected option when the primary is directly cleared', async () => {
    get.mockResolvedValue(optionA)
    list.mockResolvedValue([optionA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA,
    }, global: { stubs: { ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' }, NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button', NSelect: true, NInputNumber: true, NDatePicker: true, NInput: true } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', optionA.id)
    await picker.vm.$emit('update:instrument', optionA)
    await flushPromises()
    await wrapper.setProps({ primaryInstrument: null })
    await flushPromises()
    expect(picker.props('modelValue')).toBeNull()
    expect(warning).toHaveBeenCalledWith(expect.stringContaining('primary instrument was removed'))
  })

  it('clears a stock option after asynchronous resolution to forex and retains other trade fields', async () => {
    get.mockResolvedValue(optionA)
    list.mockResolvedValue([optionA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA,
    }, global: { stubs: {
      ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' },
      NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button',
      NSelect: SelectStub, NInputNumber: NumberStub, NDatePicker: 'input', NInput: TextareaStub,
    } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', optionA.id)
    await picker.vm.$emit('update:instrument', optionA)
    await flushPromises()
    const numbers = wrapper.findAllComponents(NumberStub)
    await numbers[0].vm.$emit('update:value', 2)
    await numbers[1].vm.$emit('update:value', 3.25)
    await numbers[2].vm.$emit('update:value', 1.5)
    await numbers[3].vm.$emit('update:value', 0.75)
    await wrapper.findAllComponents(SelectStub)[1].vm.$emit('update:value', 'bto')
    ;(wrapper.vm as unknown as { notes: string }).notes = 'keep these notes'

    await wrapper.setProps({ primaryInstrumentLoading: true })
    await wrapper.setProps({ primaryInstrument: { ...stockA, id: 'eur-usd', kind: 'forex', option: null }, primaryInstrumentLoading: false })
    await flushPromises()

    expect(picker.props('modelValue')).toBeNull()
    expect(warning).toHaveBeenCalledWith(expect.stringContaining('no compatible underlying'))
    const vm = wrapper.vm as unknown as { validate: () => string | null; toPayload: () => Record<string, unknown> }
    expect(vm.validate()).toBe('Instrument is required')
    const payload = vm.toPayload()
    expect(payload).toMatchObject({ quantity: 2, price: 3.25, commission: 1.5, fees: 0.75, action: 'bto', notes: 'keep these notes' })
  })

  it('keeps a selected stock instrument when the primary resolves to forex', async () => {
    get.mockResolvedValue(stockA)
    list.mockResolvedValue([stockA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA,
    }, global: { stubs: {
      ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' },
      NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button',
      NSelect: SelectStub, NInputNumber: NumberStub, NDatePicker: 'input', NInput: TextareaStub,
    } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', stockA.id)
    await picker.vm.$emit('update:instrument', stockA)
    await flushPromises()

    await wrapper.setProps({ primaryInstrumentLoading: true })
    await wrapper.setProps({ primaryInstrument: { ...stockA, id: 'eur-usd', kind: 'forex', option: null }, primaryInstrumentLoading: false })
    await flushPromises()

    expect(picker.props('modelValue')).toBe(stockA.id)
  })

  it('blocks retained options during resolution failure and loading, then retries by exact underlying', async () => {
    get.mockResolvedValue(optionA)
    list.mockResolvedValue([optionA])
    const wrapper = mount(TradeLegRow, { props: {
      accountId: 'account', removable: false, primaryInstrument: stockA,
    }, global: { stubs: { ...pickerStubs, NCard: { template: '<div><slot /></div>' }, NGrid: { template: '<div><slot /></div>' }, NGridItem: { template: '<div><slot /></div>' }, NText: 'span', NTag: 'span', NButton: 'button', NSelect: true, NInputNumber: true, NDatePicker: true, NInput: true } } })
    const picker = wrapper.findComponent(InstrumentPicker)
    await picker.vm.$emit('update:modelValue', optionA.id)
    await picker.vm.$emit('update:instrument', optionA)
    await flushPromises()
    await wrapper.setProps({ primaryInstrumentLoading: true })
    expect((wrapper.vm as unknown as { validate: () => string | null }).validate()).toContain('Resolve the primary instrument')
    expect(picker.props('modelValue')).toBe(optionA.id)

    await wrapper.setProps({ primaryInstrumentLoading: false, primaryInstrumentError: 'temporary failure' })
    expect((wrapper.vm as unknown as { validate: () => string | null }).validate()).toContain('Resolve the primary instrument')
    await wrapper.setProps({ primaryInstrumentError: null, primaryInstrument: { ...stockA, id: 'stock-a-retry' } })
    await flushPromises()
    expect(picker.props('modelValue')).toBeNull()
  })
})
