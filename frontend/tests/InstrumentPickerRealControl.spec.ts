import { mount, flushPromises } from '@vue/test-utils'
import { NButton, NCheckbox, NMessageProvider, NSelect } from 'naive-ui'
import { defineComponent, h } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import InstrumentPicker from '../src/components/InstrumentPicker.vue'

const stockA = { id: 'a', kind: 'stock', symbol: 'AAA', exchange: 'X', currency: 'USD', name: null, option: null }
const stockB = { id: 'b', kind: 'stock', symbol: 'BBB', exchange: 'X', currency: 'USD', name: null, option: null }
const showEvents: boolean[] = []

const ObservedRealSelect = defineComponent({
  inheritAttrs: false,
  emits: ['update:show'],
  setup(_, { attrs, emit, slots }) {
    return () => h(NSelect, {
      ...attrs,
      onUpdateShow: (show: boolean) => {
        showEvents.push(show)
        emit('update:show', show)
      },
    }, slots)
  },
})

afterEach(() => {
  vi.unstubAllGlobals()
  showEvents.length = 0
})

describe('InstrumentPicker with the real Naive Select', () => {
  it('reopens after a primary switch and requests candidates with a cleared search', async () => {
    const calls: URL[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      const url = new URL(input, 'http://localhost')
      calls.push(url)
      const rows = url.searchParams.get('related_underlying_id') === 'b' ? [stockB] : [stockA]
      return new Response(JSON.stringify(rows), { status: 200, headers: { 'content-type': 'application/json' } })
    }))
    const Harness = defineComponent({
      props: ['underlying'],
      setup(props) {
        return () => h(NMessageProvider, null, {
          default: () => h(InstrumentPicker, {
            modelValue: null,
            optionUnderlyingId: props.underlying,
            relatedUnderlyingId: props.underlying,
            searchContextKey: props.underlying,
          }),
        })
      },
    })
    const wrapper = mount(Harness, {
      props: { underlying: 'a' },
      attachTo: document.body,
      global: {
        components: { 'n-select': ObservedRealSelect, 'n-button': NButton, 'n-checkbox': NCheckbox },
        stubs: { InstrumentForm: true },
      },
    })

    try {
      await wrapper.get('.n-base-selection-label').trigger('click')
      await flushPromises()
      expect(calls.at(-1)?.searchParams.get('related_underlying_id')).toBe('a')

      await wrapper.get('input').setValue('AAA')
      await new Promise(resolve => setTimeout(resolve, 350))
      await flushPromises()
      expect(calls.at(-1)?.searchParams.get('q')).toBe('AAA')

      await wrapper.setProps({ underlying: 'b' })
      await flushPromises()
      expect(wrapper.getComponent(NSelect).props('options')).toEqual([{ label: 'BBB (X) [stock]', value: 'b' }])
      expect(wrapper.get('input').element.value).toBe('')
      expect(calls.at(-1)?.searchParams.get('q')).toBeNull()
      expect(calls.filter(url => url.searchParams.get('related_underlying_id') === 'b')
        .every(url => url.searchParams.get('q') === null)).toBe(true)

      document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
      document.body.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
      await flushPromises()
      const count = calls.length
      await wrapper.get('.n-base-selection-label').trigger('click')
      await flushPromises()

      expect(showEvents).toEqual([true, true])
      expect(calls.length).toBeGreaterThan(count)
      expect(calls.at(-1)?.searchParams.get('related_underlying_id')).toBe('b')
      expect(calls.at(-1)?.searchParams.get('q')).toBeNull()
    } finally {
      wrapper.unmount()
    }
  })
})
