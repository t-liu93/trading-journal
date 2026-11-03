import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TradeEntryModal from '../src/components/TradeEntryModal.vue'
import PositionFormModal from '../src/components/PositionFormModal.vue'
import type { Instrument } from '../src/api/instruments'
import type { Position } from '../src/api/positions'
import { ApiError } from '../src/api/types'

const { createPosition, createTrade, createMany, listAccounts, getInstrument, warning, error } = vi.hoisted(() => ({
  createPosition: vi.fn(), createTrade: vi.fn(), createMany: vi.fn(), listAccounts: vi.fn(), getInstrument: vi.fn(), warning: vi.fn(), error: vi.fn(),
}))
vi.mock('../src/api/positions', async (load) => ({ ...await load(), positionsApi: { create: createPosition, update: vi.fn() } }))
vi.mock('../src/api/trades', async (load) => ({ ...await load(), tradesApi: { create: createTrade, createMany } }))
vi.mock('../src/api/accounts', async (load) => ({ ...await load(), accountsApi: { list: listAccounts } }))
vi.mock('../src/api/instruments', async (load) => ({ ...await load(), instrumentsApi: { get: getInstrument, list: vi.fn() } }))
vi.mock('naive-ui', async (load) => ({ ...await load(), useMessage: () => ({ success: vi.fn(), warning, error }) }))

const stock: Instrument = { id: 'stock-1', kind: 'stock', symbol: 'AAPL', exchange: 'NASDAQ', currency: 'USD', created_at: '', option: null }
const position: Position = {
  id: 'position-1', account_id: 'account-1', primary_instrument_id: stock.id, strategy_type: 'spot_stock', status: 'open',
  opened_at: '2026-11-03T10:00:00Z', closed_at: null, capital_used: null, max_risk_at_open: null, max_reward_at_open: null,
  realized_pnl: null, notes: null, created_at: '', updated_at: '',
}

const Button = defineComponent({
  props: { disabled: Boolean, loading: Boolean, type: String }, emits: ['click'],
  setup(_, { slots, emit, attrs }) { return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.()) },
})
const Passthrough = defineComponent({ setup(_, { slots, attrs }) { return () => h('div', attrs, slots.default?.()) } })
const Modal = defineComponent({ setup(_, { slots, attrs }) { return () => h('div', attrs, [slots.default?.(), slots.footer?.()]) } })
const Text = defineComponent({ setup(_, { slots, attrs }) { return () => h('span', attrs, slots.default?.()) } })
const NumberInput = defineComponent({
  props: { value: Number, modelValue: Number, placeholder: String }, emits: ['update:value', 'update:modelValue'],
  setup(props, { emit, attrs }) { return () => h('input', { ...attrs, type: 'number', value: props.value ?? props.modelValue ?? '', onInput: (e: Event) => {
    const value = Number((e.target as HTMLInputElement).value)
    emit('update:value', value); emit('update:modelValue', value)
  } }) },
})
const Input = defineComponent({
  props: { value: String, modelValue: String, type: String }, emits: ['update:value', 'update:modelValue'],
  setup(props, { emit, attrs }) { return () => h(props.type === 'textarea' ? 'textarea' : 'input', { ...attrs, value: props.value ?? props.modelValue ?? '', onInput: (e: Event) => {
    const value = (e.target as HTMLInputElement).value
    emit('update:value', value); emit('update:modelValue', value)
  } }) },
})
const Select = defineComponent({
  props: { value: String, options: Array, placeholder: String }, emits: ['update:value'],
  setup(props, { emit, attrs }) { return () => h('select', { ...attrs, value: props.value ?? '', onChange: (e: Event) => emit('update:value', (e.target as HTMLSelectElement).value || null) }, [
    h('option', { value: '' }, props.placeholder ?? ''), ...((props.options ?? []) as Array<{ label: string; value: string }>).map(option => h('option', { value: option.value }, option.label)),
  ]) },
})
const InstrumentPickerStub = defineComponent({
  props: ['modelValue', 'allowCreate', 'disabled'], emits: ['update:modelValue', 'update:instrument'],
  setup(_, { emit }) { return () => h('button', { 'data-test': 'choose-stock', onClick: () => { emit('update:modelValue', stock.id); emit('update:instrument', stock) } }, 'Choose AAPL') },
})
const FormStub = defineComponent({ emits: ['submit'], setup(_, { slots, expose }) { expose({ validate: () => Promise.resolve(true) }); return () => h('form', { onSubmit: (e: Event) => { e.preventDefault() } }, slots.default?.()) } })
const NumberWithFocus = defineComponent({
  props: { value: Number, options: Array }, emits: ['update:value', 'focus'],
  setup(props, { emit, attrs }) { return () => h('input', { ...attrs, value: props.value ?? '', role: 'combobox', onFocus: () => emit('focus'), onInput: (e: Event) => emit('update:value', Number((e.target as HTMLInputElement).value)) }) },
})
const DatePicker = defineComponent({
  props: { value: Number, clearable: Boolean }, emits: ['update:value'],
  setup(props, { emit }) { return () => h('div', [
    h('input', { type: 'datetime-local', value: new Date(props.value ?? Date.now()).toISOString().slice(0, 16), onInput: () => emit('update:value', Date.now()) }),
    ...(props.clearable ? [h('button', { 'aria-label': 'Clear trade date', onClick: () => emit('update:value', null) }, 'Clear date')] : []),
  ]) },
})
const commonStubs = {
  NButton: Button, NText: Text, NTag: Text, NCard: Passthrough, NGrid: Passthrough, NGridItem: Passthrough,
  NSelect: Select, NInputNumber: NumberInput, NDatePicker: DatePicker, NInput: Input, NAlert: Passthrough,
  NDivider: Passthrough, NH4: Text, NModal: Modal, NForm: FormStub, NFormItem: Passthrough,
  InstrumentPicker: InstrumentPickerStub, NSpin: Passthrough,
}

function mountTradeEntry(positionId = 'position-1') {
  return mount(TradeEntryModal, { attachTo: document.body, props: { accountId: 'account-1', positionId }, global: { stubs: commonStubs } })
}

describe('trade entry form interactions', () => {
  beforeEach(() => {
    createPosition.mockReset().mockResolvedValue(position)
    createTrade.mockReset().mockResolvedValue([])
    createMany.mockReset().mockResolvedValue([])
    listAccounts.mockReset().mockResolvedValue([{ id: 'account-1', name: 'Main', base_currency: 'USD', archived_at: null }])
    getInstrument.mockReset().mockResolvedValue(stock)
    warning.mockReset(); error.mockReset()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
  })

  it('shows the missing field on the first leg, scrolls and focuses its control', async () => {
    const wrapper = mountTradeEntry()
    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(wrapper.get('[data-leg-id] [data-field="instrument"] button').element)
    expect(wrapper.get('[data-field="instrument"] [role="alert"]').text()).toContain('Instrument is required')
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
    expect(warning).toHaveBeenCalledWith(expect.stringContaining('Leg 1'))
    expect(createTrade).not.toHaveBeenCalled()
  })

  it('rejects a cleared trade date without serializing it as a timestamp', async () => {
    const wrapper = mountTradeEntry()
    await wrapper.get('[aria-label="Clear trade date"]').trigger('click')
    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-field="executed_at"] [role="alert"]').text()).toContain('Trade date and time is required')
    expect(createTrade).not.toHaveBeenCalled()
    expect(createMany).not.toHaveBeenCalled()
  })

  it('submits the valid Unix epoch date as an ISO timestamp', async () => {
    const wrapper = mountTradeEntry()
    await wrapper.get('[data-test="choose-stock"]').trigger('click')
    await wrapper.get('select').setValue('buy')
    const numbers = wrapper.findAll('input[type="number"]')
    await numbers[0]!.setValue('1')
    await numbers[1]!.setValue('10')
    wrapper.findComponent(DatePicker).vm.$emit('update:value', 0)
    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(createTrade).toHaveBeenCalledTimes(1)
    expect(createTrade.mock.calls[0]![0].executed_at).toBe('1970-01-01T00:00:00.000Z')
  })

  it('submits a valid timestamp before the Unix epoch', async () => {
    const wrapper = mountTradeEntry()
    await wrapper.get('[data-test="choose-stock"]').trigger('click')
    await wrapper.get('select').setValue('buy')
    const numbers = wrapper.findAll('input[type="number"]')
    await numbers[0]!.setValue('1')
    await numbers[1]!.setValue('10')
    wrapper.findComponent(DatePicker).vm.$emit('update:value', -1000)
    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(createTrade).toHaveBeenCalledTimes(1)
    expect(createTrade.mock.calls[0]![0].executed_at).toBe('1969-12-31T23:59:59.000Z')
  })

  it('retains entered values in every leg through add, remove and validation, and submits matching previews', async () => {
    const wrapper = mountTradeEntry()
    await wrapper.findAll('button').find(button => button.text() === '+ Add leg')!.trigger('click')
    expect(wrapper.findAll('[data-leg-id]')).toHaveLength(2)

    for (const [index, leg] of wrapper.findAll('[data-leg-id]').entries()) {
      await leg.get('[data-test="choose-stock"]').trigger('click')
      await leg.get('select').setValue('buy')
      const numbers = leg.findAll('input[type="number"]')
      await numbers[0].setValue(String(index + 1))
      await numbers[1].setValue(index === 0 ? '12.5' : '20')
      await numbers[2].setValue('1')
      await numbers[3].setValue('0.5')
      await leg.get('textarea').setValue(`note ${index + 1}`)
    }

    const previewText = wrapper.text()
    expect(previewText).toContain('Estimated cash received or paid')
    expect(previewText).toContain('-14.00')
    expect(previewText).toContain('-41.50')
    const secondRemove = wrapper.findAll('[data-leg-id]')[1]!.find('button')
    expect(secondRemove.exists()).toBe(true)
    // Remove the second leg after it has retained all its values, then add it back and verify first-leg data remains.
    await secondRemove.trigger('click')
    expect(wrapper.findAll('[data-leg-id]')).toHaveLength(1)
    expect(wrapper.get('[data-field="quantity"] input').element).toHaveProperty('value', '1')
    expect(wrapper.get('textarea').element).toHaveProperty('value', 'note 1')
    await wrapper.findAll('button').find(button => button.text() === '+ Add leg')!.trigger('click')
    const second = wrapper.findAll('[data-leg-id]')[1]!
    await second.get('[data-test="choose-stock"]').trigger('click')
    await second.get('select').setValue('sell')
    const numbers = second.findAll('input[type="number"]')
    await numbers[0].setValue('3')
    await numbers[1].setValue('10')
    await second.get('textarea').setValue('second retained')

    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(createMany).toHaveBeenCalledTimes(1)
    const rows = createMany.mock.calls[0]![0] as Array<Record<string, unknown>>
    expect(rows).toHaveLength(2)
    expect(rows.map(row => ({ action: row.action, quantity: row.quantity, price: row.price, fees: row.fees, notes: row.notes }))).toEqual([
      { action: 'buy', quantity: 1, price: 12.5, fees: 0.5, notes: 'note 1' },
      { action: 'sell', quantity: 3, price: 10, fees: 0, notes: 'second retained' },
    ])
    expect(rows[0]).toMatchObject({ commission: 1, fees: 0.5, executed_at: expect.stringMatching(/^\d{4}-\d\d-\d\dT/) })
    expect(createTrade).not.toHaveBeenCalled()
  })

  it('reuses an already-created Position after a first-trade failure and keeps the entered form values', async () => {
    createMany.mockRejectedValueOnce(new Error('temporary trade endpoint failure')).mockResolvedValueOnce([])
    const wrapper = mount(PositionFormModal, { props: { show: true, mode: 'create' }, global: { stubs: commonStubs } })
    await flushPromises()
    await wrapper.get('[data-test="choose-stock"]').trigger('click') // primary instrument
    await wrapper.get('select').setValue('account-1')
    const selects = wrapper.findAll('select')
    await selects[1]!.setValue('spot_stock')
    await wrapper.get('[data-leg-id] [data-test="choose-stock"]').trigger('click')
    await wrapper.get('[data-leg-id] select').setValue('buy')
    const nums = wrapper.findAll('[data-leg-id] input[type="number"]')
    await nums[0]!.setValue('4')
    await nums[1]!.setValue('25')
    await wrapper.get('[data-leg-id] textarea').setValue('retry note')
    await wrapper.findAll('button').find(button => button.text() === '+ Add leg')!.trigger('click')
    const secondLeg = wrapper.findAll('[data-leg-id]')[1]!
    await secondLeg.get('[data-test="choose-stock"]').trigger('click')
    await secondLeg.get('select').setValue('sell')
    const secondNums = secondLeg.findAll('input[type="number"]')
    await secondNums[0]!.setValue('2')
    await secondNums[1]!.setValue('30')
    await secondLeg.get('textarea').setValue('second leg survives retry')

    await wrapper.findAll('button').find(button => button.text() === 'Create')!.trigger('click')
    await flushPromises()
    expect(createPosition).toHaveBeenCalledTimes(1)
    expect(createMany).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Position was already created')
    expect(wrapper.get('[data-leg-id] textarea').element).toHaveProperty('value', 'retry note')
    expect(wrapper.findAll('[data-leg-id] textarea')[1]!.element).toHaveProperty('value', 'second leg survives retry')
    expect(wrapper.findAll('select')[0]!.attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('select')[1]!.attributes('disabled')).toBeDefined()

    await wrapper.findAll('button').find(button => button.text() === 'Create')!.trigger('click')
    await flushPromises()
    expect(createPosition).toHaveBeenCalledTimes(1)
    expect(createMany).toHaveBeenCalledTimes(2)
    expect(createMany.mock.calls[1]![0]).toEqual([
      expect.objectContaining({ position_id: position.id, action: 'buy', quantity: 4, price: 25, notes: 'retry note' }),
      expect.objectContaining({ position_id: position.id, action: 'sell', quantity: 2, price: 30, notes: 'second leg survives retry' }),
    ])
  })

  it('maps structured API field errors back to the affected field and preserves input for retry', async () => {
    createTrade.mockRejectedValueOnce(new ApiError(422, [{ loc: ['body', 'quantity'], msg: 'Input should be greater than 0' }], 'Invalid trade'))
    const wrapper = mountTradeEntry()
    const leg = wrapper.get('[data-leg-id]')
    await leg.get('[data-test="choose-stock"]').trigger('click')
    await leg.get('select').setValue('buy')
    const nums = leg.findAll('input[type="number"]')
    await nums[0]!.setValue('2')
    await nums[1]!.setValue('9')
    await leg.get('textarea').setValue('keep after API error')
    await wrapper.findAll('button').find(button => button.text() === 'Submit')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-field="quantity"] [role="alert"]').text()).toContain('greater than 0')
    expect(leg.get('[data-field="quantity"] input').element).toBe(document.activeElement)
    expect(leg.get('textarea').element).toHaveProperty('value', 'keep after API error')
  })
})
