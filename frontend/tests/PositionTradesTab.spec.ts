import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PositionTradesTab from '../src/components/PositionTradesTab.vue'
import type { Trade } from '../src/api/trades'

const { list, remove, getInstrument, success, error } = vi.hoisted(() => ({
  list: vi.fn(),
  remove: vi.fn(),
  getInstrument: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('../src/api/trades', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/trades')>()
  return { ...actual, tradesApi: { ...actual.tradesApi, list, remove } }
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

function mountTab() {
  return mount(PositionTradesTab, {
    props: { positionId: 'position-1', accountId: 'account-1' },
    global: { stubs: {
      NButton: Button, NPopconfirm: Popconfirm, NSpin: Passthrough, NList: Passthrough,
      NListItem: Passthrough, NTable: Passthrough, NAlert: Passthrough, NEmpty: Passthrough,
      NText: Passthrough, NTag: Passthrough, NTooltip: Passthrough, NInput: Passthrough,
      TradeActionBadge: true, TradeEntryModal: true,
    } },
  })
}

describe('PositionTradesTab archive behavior', () => {
  beforeEach(() => {
    list.mockReset().mockResolvedValue([trade])
    remove.mockReset().mockResolvedValue(null)
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
})
