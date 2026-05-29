import type { Trade } from '../api/trades'
import type { Instrument } from '../api/instruments'

export type PatternBadge = 'assignment' | 'exercise' | 'expiration' | 'ic-open' | null

export function detectPattern(
  group: Trade[],
  instrumentMap: Record<string, Instrument>,
): PatternBadge {
  if (group.length === 0) return null

  const enriched = group.map(t => ({
    trade: t,
    instrument: instrumentMap[t.instrument_id],
  }))

  // IC-open: 4 option legs in one group, no stock
  if (
    group.length === 4 &&
    enriched.every(e => e.instrument?.kind === 'option') &&
    enriched.every(e => e.trade.action === 'sto' || e.trade.action === 'bto')
  ) {
    return 'ic-open'
  }

  const options = enriched.filter(e => e.instrument?.kind === 'option')
  const stocks = enriched.filter(e => e.instrument?.kind === 'stock')

  // Expiration: single option leg, price=0
  if (group.length === 1 && options.length === 1 && Number(group[0].price) === 0) {
    return 'expiration'
  }

  // Assignment / Exercise: 1 option close @0 + 1 stock fill
  // Per data-model §4.5.2:
  //   assignment: btc put @0 + buy stock | btc call @0 + sell stock
  //   exercise:   stc call @0 + buy stock | stc put @0 + sell stock
  if (group.length === 2 && options.length === 1 && stocks.length === 1) {
    const optTrade = options[0].trade
    const optType = options[0].instrument?.option?.opt_type
    const stockAction = stocks[0].trade.action
    const isOptClose = optTrade.action === 'btc' || optTrade.action === 'stc'

    if (isOptClose && Number(optTrade.price) === 0 && optType) {
      if (optTrade.action === 'btc') {
        // Assignment: closing short option
        //   short put assigned  → buy stock (put holder exercises, you buy at strike)
        //   short call assigned → sell stock (call holder exercises, you sell at strike)
        if ((optType === 'put' && stockAction === 'buy') ||
            (optType === 'call' && stockAction === 'sell')) {
          return 'assignment'
        }
      } else {
        // stc: Exercise: closing long option
        //   long call exercised → buy stock (you exercise, buy at strike)
        //   long put exercised  → sell stock (you exercise, sell at strike)
        if ((optType === 'call' && stockAction === 'buy') ||
            (optType === 'put' && stockAction === 'sell')) {
          return 'exercise'
        }
      }
    }
  }

  return null
}
