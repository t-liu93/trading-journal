import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PositionTradesTab from '../src/components/PositionTradesTab.vue'
import type { Trade } from '../src/api/trades'

const { list, remove, update, getInstrument, success, error } = vi.hoisted(() => ({
  list: vi.fn(),
  remove: vi.fn(),
  update: vi.fn(),
  getInstrument: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('../src/api/trades', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/trades')>()
  return { ...actual, tradesApi: { ...actual.tradesApi, list, remove, update } }
})
vi.mock('../src/api/instruments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/instruments')>()
  return { ...actual, instrumentsApi: { ...actual.instrumentsApi, get: getInstrument } }
})
vi.mock('naive-ui', () => ({ useMessage: () => ({ success, error }) }))

const trade: Trade = {
  id: 'trade-1', position_id: 'position-1', account_id: 'account-1', instrument_id: 'instrument-1',
  action: 'buy', quantity: '10', price: '10', commission: '0', fees: '0', cash_flow: '-100',
  executed_at: '2026-05-01T00:00:00Z', order_group_id: null, archived_at: null, notes: null,
}

const Button = defineComponent({
  setup(_, { slots, attrs }) { return () => h('button', attrs, slots.default?.()) },
})
const Popconfirm = defineComponent({
  emits: ['positive-click'],
  setup(_, { slots, emit }) {
    return () => h('div', [slots.trigger?.(), slots.default?.(), h('button', {
      'data-test': 'confirm-archive', onClick: () => emit('positive-click'),
    }, 'Confirm archive')])
  },
})
const Passthrough = defineComponent({ setup(_, { slots }) { return () => h('div', slots.default?.()) } })
const TextareaInput = defineComponent({
  props: { value: String, modelValue: String, type: String, disabled: Boolean, ariaLabel: String },
  emits: ['update:value', 'update:modelValue'],
  setup(props, { emit, attrs }) {
    return () => h('textarea', {
      ...attrs,
      value: props.value ?? props.modelValue ?? '',
      disabled: props.disabled,
      'aria-label': props.ariaLabel,
      onInput: (event: Event) => {
        const value = (event.target as HTMLTextAreaElement).value
        emit('update:value', value)
        emit('update:modelValue', value)
      },
    })
  },
})

function mountTab() {
  return mount(PositionTradesTab, {
    props: { positionId: 'position-1', accountId: 'account-1' },
    global: { stubs: {
      NButton: Button, NPopconfirm: Popconfirm, NSpin: Passthrough, NList: Passthrough,
      NListItem: Passthrough, NTable: Passthrough, NAlert: Passthrough, NEmpty: Passthrough, NSwitch: Passthrough,
      NText: Passthrough, NTag: Passthrough, NTooltip: Passthrough, NInput: TextareaInput,
      TradeActionBadge: true, TradeEntryModal: true,
    } },
  })
}

describe('PositionTradesTab archive behavior', () => {
  beforeEach(() => {
    list.mockReset().mockResolvedValue([trade])
    remove.mockReset().mockResolvedValue(null)
    update.mockReset().mockResolvedValue(trade)
    getInstrument.mockReset().mockResolvedValue({ id: 'instrument-1', kind: 'stock', symbol: 'AAPL', exchange: 'NASDAQ', currency: 'USD', name: 'Apple', option: null })
    success.mockReset()
    error.mockReset()
  })

  it('archives through the API, refreshes active Trades, and notifies the parent', async () => {
    const wrapper = mountTab()
    await flushPromises()
    list.mockClear()
    await wrapper.get('[data-test="confirm-archive"]').trigger('click')
    await flushPromises()
    expect(remove).toHaveBeenCalledWith('trade-1')
    expect(list).toHaveBeenCalledWith({ position_id: 'position-1', include_archived: false })
    expect(wrapper.emitted('trades-changed')).toHaveLength(1)
    expect(success).toHaveBeenCalledWith('Trade archived')
    expect(error).not.toHaveBeenCalled()
  })

  it('keeps archive success distinct from a failed refresh and exposes retry', async () => {
    const wrapper = mountTab()
    await flushPromises()
    list.mockClear().mockRejectedValueOnce(new Error('offline'))
    await wrapper.get('[data-test="confirm-archive"]').trigger('click')
    await flushPromises()
    expect(remove).toHaveBeenCalledWith('trade-1')
    expect(wrapper.emitted('trades-changed')).toHaveLength(1)
    expect(success).toHaveBeenCalledWith('Trade archived')
    expect(error).not.toHaveBeenCalledWith('Failed to archive trade')
    expect(wrapper.text()).toContain('Retry')
    list.mockResolvedValueOnce([])
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Retry')
    expect(retry).toBeDefined()
    await retry!.trigger('click')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('renders notes directly after each Trade row across all columns, including repeated instruments', async () => {
    const first = { ...trade, id: 'trade-a', order_group_id: 'order-1', notes: 'first note' }
    const second = { ...trade, id: 'trade-b', order_group_id: 'order-1', notes: 'second note' }
    const empty = { ...trade, id: 'trade-c', order_group_id: 'order-1', instrument_id: 'instrument-2', notes: null }
    list.mockResolvedValueOnce([first, second, empty])
    const wrapper = mountTab()
    await flushPromises()

    const rows = wrapper.findAll('tbody > tr')
    expect(rows.map((row) => row.attributes('data-notes-for') ?? row.attributes('data-trade-id'))).toEqual([
      'trade-a', 'trade-a', 'trade-b', 'trade-b', 'trade-c',
    ])
    expect(rows[1].element.previousElementSibling).toBe(rows[0].element)
    expect(rows[3].element.previousElementSibling).toBe(rows[2].element)
    expect(rows[1].find('td').attributes('colspan')).toBe('7')
    expect(rows[3].find('td').attributes('colspan')).toBe('7')
    expect(wrapper.text()).toContain('first note')
    expect(wrapper.text()).toContain('second note')
    expect(wrapper.findAll('[data-notes-for="trade-c"]')).toHaveLength(0)
  })

  it('keeps multiline, long, and HTML-like notes as wrapped plain text', async () => {
    const notes = `line one\n${'long-word-'.repeat(30)}\n<b onclick="alert(1)">literal</b>`
    list.mockResolvedValueOnce([{ ...trade, notes }])
    const wrapper = mountTab()
    await flushPromises()

    const noteRow = wrapper.get('[data-notes-for="trade-1"]')
    expect(noteRow.text()).toBe(notes)
    expect(noteRow.find('b').exists()).toBe(false)
    expect(noteRow.find('td').classes()).toContain('trade-notes-cell')
    expect(noteRow.find('.trade-notes-text').attributes('style')).toBeUndefined()
  })

  it('saves by button and Ctrl/Command+Enter, and clears notes with a null payload', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    const input = wrapper.get('textarea')
    expect(input.element.tagName).toBe('TEXTAREA')
    await input.setValue('updated\nsecond line')
    await input.trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()
    expect(update).toHaveBeenCalledWith('trade-1', { notes: 'updated\nsecond line' })
    expect(success).toHaveBeenCalledWith('Notes updated')

    list.mockResolvedValueOnce([{ ...trade, notes: 'to clear' }])
    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    await wrapper.get('textarea').setValue('saved with command enter')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', metaKey: true })
    await flushPromises()
    expect(update).toHaveBeenLastCalledWith('trade-1', { notes: 'saved with command enter' })

    list.mockResolvedValueOnce([{ ...trade, notes: 'to clear' }])
    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    await wrapper.get('textarea').setValue('')
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenLastCalledWith('trade-1', { notes: null })
  })

  it('cancels edits and preserves input after failure for retry', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    await wrapper.get('textarea').setValue('unsaved text')
    await wrapper.findAll('button').find((button) => button.text() === 'Cancel')!.trigger('click')
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('unsaved text')

    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    await wrapper.get('textarea').setValue('retry this')
    update.mockRejectedValueOnce(new Error('offline'))
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('textarea').element).toHaveProperty('value', 'retry this')
    expect(error).toHaveBeenCalledWith('Failed to update notes')
    update.mockResolvedValueOnce(trade)
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenLastCalledWith('trade-1', { notes: 'retry this' })
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('keeps another Trade edit intact when a prior save resolves late', async () => {
    let resolveSave!: (value: Trade) => void
    update.mockImplementationOnce(() => new Promise<Trade>((resolve) => { resolveSave = resolve }))
    const trades = [{ ...trade, id: 'trade-a' }, { ...trade, id: 'trade-b', instrument_id: 'instrument-2' }]
    list.mockResolvedValueOnce(trades).mockResolvedValue(trades)
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Edit notes')!.trigger('click')
    await wrapper.get('textarea').setValue('saved A')
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await wrapper.get('[data-trade-id="trade-b"]').find('button').trigger('click')
    await wrapper.get('textarea').setValue('draft for B')
    resolveSave(trade)
    await flushPromises()
    expect(wrapper.get('textarea').element).toHaveProperty('value', 'draft for B')
  })

  it('keeps each Trade busy until its own save finishes when another Trade saves first', async () => {
    let resolveSaveA!: (value: Trade) => void
    update.mockImplementationOnce(() => new Promise<Trade>((resolve) => { resolveSaveA = resolve }))
    const trades = [{ ...trade, id: 'trade-a' }, { ...trade, id: 'trade-b', instrument_id: 'instrument-2' }]
    list.mockResolvedValueOnce(trades).mockResolvedValue(trades)
    const wrapper = mountTab()
    await flushPromises()

    await wrapper.get('[data-trade-id="trade-a"]').find('button').trigger('click')
    await wrapper.get('textarea').setValue('save A')
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await wrapper.get('[data-trade-id="trade-b"]').find('button').trigger('click')
    await wrapper.get('textarea').setValue('save B')
    await wrapper.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()

    const editA = wrapper.get('[data-trade-id="trade-a"]').find('button')
    expect(editA.attributes('disabled')).toBeDefined()
    resolveSaveA(trade)
    await flushPromises()
    expect(wrapper.get('[data-trade-id="trade-a"]').find('button').attributes('disabled')).toBeUndefined()
  })

  it('exits editing on readonly transition and does not enable archived Trade editing', async () => {
    list.mockResolvedValueOnce([{ ...trade, id: 'trade-active' }, { ...trade, id: 'trade-archived', archived_at: '2026-01-01T00:00:00Z', notes: 'archived note' }])
    const wrapper = mount(PositionTradesTab, {
      props: { positionId: 'position-1', accountId: 'account-1', readonly: false },
      global: { stubs: {
        NButton: Button, NPopconfirm: Popconfirm, NSpin: Passthrough, NList: Passthrough,
        NListItem: Passthrough, NTable: Passthrough, NAlert: Passthrough, NEmpty: Passthrough, NSwitch: Passthrough,
        NText: Passthrough, NTag: Passthrough, NTooltip: Passthrough, NInput: TextareaInput,
        TradeActionBadge: true, TradeEntryModal: true,
      } },
    })
    await flushPromises()
    const editButtons = wrapper.findAll('button').filter((button) => button.text() === 'Edit notes')
    expect(editButtons[1].attributes('disabled')).toBeDefined()
    await editButtons[0].trigger('click')
    await wrapper.setProps({ readonly: true })
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.findAll('button').filter((button) => button.text() === 'Edit notes').every((button) => button.attributes('disabled') !== undefined)).toBe(true)
  })

  it('hides Archive for the Trade while its notes editor is open', async () => {
    const wrapper = mountTab()
    await flushPromises()
    const row = wrapper.get('[data-trade-id="trade-1"]')
    await row.find('button').trigger('click')
    expect(row.findAll('button').some((button) => button.text() === 'Archive')).toBe(false)
    expect(wrapper.find('[data-test="confirm-archive"]').exists()).toBe(false)
    await wrapper.findAll('button').find((button) => button.text() === 'Cancel')!.trigger('click')
    expect(wrapper.findAll('button').some((button) => button.text() === 'Archive')).toBe(true)
    await wrapper.get('[data-test="confirm-archive"]').trigger('click')
    await flushPromises()
    expect(remove).toHaveBeenCalledWith('trade-1')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })
})
