import { afterEach, describe, expect, it, vi } from 'vitest'
import { positionsApi } from '../src/api/positions'
import { tradesApi } from '../src/api/trades'

const open = '2026-11-01T09:00:00'
const close = '2026-11-02T09:00:00'
const position = { id: 'position', opened_at: open, closed_at: close }
const trade = { id: 'trade', executed_at: open }
function json(value: unknown) {
  return new Response(JSON.stringify(value), { status: 200, headers: { 'content-type': 'application/json' } })
}
afterEach(() => vi.unstubAllGlobals())

const amsterdam = (value: string) => new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Amsterdam', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
}).format(new Date(value))

describe('Position and Trade API timestamps', () => {
  it('interprets naive stored UTC on every Position response, including create and close', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json([position]))
      .mockResolvedValueOnce(json({ ...position, closed_at: null }))
      .mockResolvedValueOnce(json(position)).mockResolvedValueOnce(json(position))
    vi.stubGlobal('fetch', fetch)
    const responses = [(await positionsApi.list())[0]!, await positionsApi.get('position'),
      await positionsApi.create({ account_id: 'account', primary_instrument_id: 'stock', strategy_type: 'spot_stock', opened_at: open + 'Z' }),
      await positionsApi.update('position', { status: 'closed' })]
    for (const row of responses) {
      expect(row.opened_at).toBe(open + 'Z')
      expect(amsterdam(row.opened_at)).toBe('10:00')
      expect(row.closed_at === null || row.closed_at === close + 'Z').toBe(true)
    }
    expect(responses[1]!.closed_at).toBeNull()
  })

  it('normalizes all Trade response paths without changing the submitted instant', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json([trade]))
      .mockResolvedValueOnce(json([trade])).mockResolvedValueOnce(json([trade])).mockResolvedValueOnce(json(trade)))
    const payload = { position_id: 'position', instrument_id: 'stock', action: 'buy' as const,
      quantity: 1, price: 1, executed_at: open + 'Z' }
    const rows = [(await tradesApi.list())[0]!, (await tradesApi.create(payload))[0]!,
      (await tradesApi.createMany([payload]))[0]!, await tradesApi.update('trade', { notes: 'keep time' })]
    expect(rows.every(row => row.executed_at === open + 'Z')).toBe(true)
    expect(JSON.parse(vi.mocked(fetch).mock.calls[1]![1]!.body as string).executed_at).toBe(open + 'Z')
  })

  it.each([
    ['2026-11-01T09:00:00Z', '10:00'],
    ['2026-11-01T10:00:00+01:00', '10:00'],
    ['2026-07-01T08:00:00', '10:00'],
    ['2026-10-25T00:30:00', '02:30'],
    ['2026-10-25T01:30:00', '02:30'],
    ['2026-11-01T23:30:00.123456', '00:30'],
  ])('preserves the instant for offset, summer, DST and midnight cases: %s', async (value, expected) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...position, opened_at: value })))
    const result = await positionsApi.get('position')
    expect(amsterdam(result.opened_at)).toBe(expected)
    if (/Z|[+-]\d\d:\d\d$/.test(value)) expect(result.opened_at).toBe(value)
  })
})
