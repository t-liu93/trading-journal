import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import type { Instrument } from '../src/api/instruments'
import PmccMetaForm from '../src/components/PmccMetaForm.vue'
import InstrumentPicker from '../src/components/InstrumentPicker.vue'

vi.mock('../src/composables/usePmccMeta', () => ({
  usePmccMeta: () => ({ meta: ref(null), loading: ref(false), refresh: vi.fn(), createOrUpdate: vi.fn(), remove: vi.fn() }),
}))
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return { ...actual, useMessage: () => ({ warning: vi.fn(), success: vi.fn(), error: vi.fn() }) }
})

const stock: Instrument = { id: 'stock-a', kind: 'stock', symbol: 'AAPL', exchange: 'NASDAQ', currency: 'USD', created_at: '', option: null }
const primaryOption: Instrument = { ...stock, id: 'primary-option', kind: 'option', option: {
  underlying_id: stock.id, opt_type: 'call', strike: '100', expiry: '2027-01-15', multiplier: 100, style: 'american',
} }
const PickerSelectStub = defineComponent({
  props: ['options', 'value', 'disabled'], emits: ['update:value', 'focus', 'update:show', 'search'],
  setup(props, { emit }) { return () => h('div', (props.options as Array<{ label: string; value: string }>).map(option => h('button', {
    key: option.value, 'data-value': option.value, onClick: () => emit('update:value', option.value),
  }, option.label))) },
})
const ContextualFormStub = defineComponent({
  props: ['show', 'underlyingInstrument', 'lockUnderlying'],
  template: '<div data-test="contextual-form" />',
})
const ButtonStub = defineComponent({ props: ['disabled', 'loading'], emits: ['click'], setup(props, { emit, slots }) { return () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()) } })
const TextStub = defineComponent({ setup(_, { slots }) { return () => h('span', slots.default?.()) } })

describe('PMCC LEAP underlying context', () => {
  it('filters LEAPs to the stock primary ID and opens contextual creation for that resolved stock', async () => {
    const wrapper = mount(PmccMetaForm, { props: { positionId: 'position', primaryInstrument: stock }, global: { stubs: {
      NSpin: { template: '<div><slot /></div>' }, NForm: { template: '<div><slot /></div>' }, NFormItem: { template: '<div><slot /></div>' },
      NText: TextStub, NAlert: { template: '<div role="alert"><slot /></div>' }, NButton: ButtonStub, NPopconfirm: { template: '<div><slot /><slot name="trigger" /></div>' },
      NSelect: PickerSelectStub, NCheckbox: { template: '<span />' }, InstrumentForm: ContextualFormStub,
    } } })
    await flushPromises()
    const picker = wrapper.findComponent(InstrumentPicker)
    expect(picker.props('kind')).toBe('option')
    expect(picker.props('allowCreate')).toBe(true)
    expect(picker.props('optionUnderlyingId')).toBe(stock.id)
    expect(picker.props('underlyingInstrument')).toEqual(stock)
    expect(picker.props('optionContextReady')).toBe(true)
    expect(picker.props('disabled')).toBe(false)
    await wrapper.get('[data-value="__create_option__"]').trigger('click')
    const form = wrapper.findComponent(ContextualFormStub)
    expect(form.props('show')).toBe(true)
    expect(form.props('underlyingInstrument')).toEqual(stock)
    expect(form.props('lockUnderlying')).toBe(true)
  })

  it('explains and blocks an option primary without weakening backend requirements', async () => {
    const wrapper = mount(PmccMetaForm, { props: { positionId: 'position', primaryInstrument: primaryOption }, global: { stubs: {
      NSpin: { template: '<div><slot /></div>' }, NForm: { template: '<div><slot /></div>' }, NFormItem: { template: '<div><slot /></div>' },
      NText: TextStub, NAlert: { template: '<div role="alert"><slot /></div>' }, NButton: ButtonStub, NPopconfirm: { template: '<div><slot /><slot name="trigger" /></div>' },
      NSelect: PickerSelectStub, NCheckbox: { template: '<span />' }, InstrumentForm: ContextualFormStub,
    } } })
    await flushPromises()
    const picker = wrapper.findComponent(InstrumentPicker)
    expect(picker.props('disabled')).toBe(true)
    expect(wrapper.text()).toContain('requires this Position\'s primary instrument to be a stock')
    expect(wrapper.findAll('button').find(button => button.text().includes('Create PMCC Meta'))?.attributes('disabled')).toBeDefined()
  })
})
