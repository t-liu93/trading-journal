import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import type { Instrument } from '../src/api/instruments'
import InstrumentForm from '../src/components/InstrumentForm.vue'

const { create } = vi.hoisted(() => ({ create: vi.fn() }))
vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, create } }
})
vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return { ...actual, useMessage: () => ({ info: vi.fn(), success: vi.fn(), error: vi.fn() }) }
})

const underlying: Instrument = { id: 'underlying-a', kind: 'stock', symbol: 'DUP', exchange: 'NYSE', currency: 'EUR', created_at: '', option: null }
const otherUnderlying: Instrument = { ...underlying, id: 'underlying-b' }
const option: Instrument = { ...underlying, id: 'option-a', kind: 'option', option: {
  underlying_id: underlying.id, opt_type: 'call', strike: '120', expiry: '2027-01-15', multiplier: 100, style: 'american',
} }
const ModalStub = defineComponent({ props: ['show'], setup(props, { slots }) { return () => props.show ? h('div', [slots.default?.(), slots.footer?.()]) : null } })
const FormStub = defineComponent({ setup(_, { slots, expose }) { expose({ validate: async () => undefined }); return () => h('div', slots.default?.()) } })
const PickerStub = defineComponent({ props: ['modelValue', 'disabled', 'kind'], emits: ['update:modelValue', 'update:instrument'], template: '<div data-test="underlying-picker" />' })
const ButtonStub = defineComponent({ props: ['loading', 'disabled'], emits: ['click'], setup(props, { emit, slots }) { return () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()) } })
const passthrough = defineComponent({ template: '<div><slot /></div>' })

function mountForm(underlyingInstrument = underlying) {
  return mount(InstrumentForm, { props: {
    show: false, initialKind: 'option', lockedKind: 'option', underlyingInstrument, lockUnderlying: true,
  }, global: { stubs: {
    NModal: ModalStub, NForm: FormStub, NRadioGroup: passthrough, NRadioButton: 'button', NFormItem: passthrough,
    NInput: defineComponent({ props: ['value', 'disabled'], template: '<input :value="value" :disabled="disabled" />' }),
    NSelect: 'select', NDatePicker: 'input', NInputNumber: 'input', NButton: ButtonStub, NText: 'span',
    CurrencySelect: { props: ['modelValue'], template: '<span data-test="currency">{{ modelValue }}</span>' },
    InstrumentPicker: PickerStub,
  } } })
}

describe('InstrumentForm contextual option creation', () => {
  it('prefills the exact underlying ID, currency and exchange and locks its picker', async () => {
    const wrapper = mountForm()
    await wrapper.setProps({ show: true })
    await flushPromises()
    const picker = wrapper.findComponent(PickerStub)
    expect(picker.props('modelValue')).toBe(underlying.id)
    expect(picker.props('disabled')).toBe(true)
    expect(wrapper.findAll('input').filter(input => input.attributes('placeholder') === 'From selected stock').map(input => (input.element as HTMLInputElement).value)).toEqual(['EUR', 'NYSE'])
    expect(wrapper.findAll('input').find(input => input.attributes('placeholder') === 'From selected stock')?.element.value).toBe('EUR')
  })

  it('sends only the existing option write contract and accepts the matching result', async () => {
    create.mockReset().mockResolvedValue({ instrument: option, existed: true })
    const wrapper = mountForm()
    await wrapper.setProps({ show: true })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === 'Create')!.trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'option', underlying_symbol: 'DUP', currency: 'EUR', underlying_exchange: 'NYSE',
    }))
    expect(create.mock.calls[0][0]).not.toHaveProperty('underlying_instrument_id')
    expect(wrapper.emitted('saved')).toEqual([[option]])
  })

  it('rejects a returned option whose exact underlying differs', async () => {
    create.mockReset().mockResolvedValue({ instrument: { ...option, option: { ...option.option!, underlying_id: 'underlying-b' } }, existed: true })
    const wrapper = mountForm()
    await wrapper.setProps({ show: true })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === 'Create')!.trigger('click')
    await flushPromises()
    expect(wrapper.emitted('saved')).toBeUndefined()
  })

  it('does not select a stale create response after contextual primary changes', async () => {
    let resolveCreate: ((value: { instrument: Instrument; existed: boolean }) => void) | undefined
    create.mockReset().mockImplementation(() => new Promise(resolve => { resolveCreate = resolve }))
    const wrapper = mountForm()
    await wrapper.setProps({ show: true })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === 'Create')!.trigger('click')
    await flushPromises()
    await wrapper.setProps({ underlyingInstrument: otherUnderlying })
    resolveCreate?.({ instrument: option, existed: true })
    await flushPromises()
    expect(wrapper.emitted('saved')).toBeUndefined()
    const picker = wrapper.findComponent(PickerStub)
    expect(picker.props('modelValue')).toBe(otherUnderlying.id)
  })
})
