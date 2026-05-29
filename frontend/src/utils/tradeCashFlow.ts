import type { TradeAction } from '../api/trades'
import type { Instrument } from '../api/instruments'

const SIGN: Record<TradeAction, -1 | 1> = {
  buy: -1, bto: -1, btc: -1,
  sell: 1, sto: 1, stc: 1,
}

export interface CashFlowRow {
  action: TradeAction
  price: number | string
  quantity: number | string
  commission?: number | string | null
  fees?: number | string | null
}

/**
 * Mirrors the backend formula in P9 §6④. Display only — never sent to
 * the server (P9 Create schema rejects client-supplied cash_flow).
 */
export function previewCashFlow(
  row: CashFlowRow,
  instrument: Pick<Instrument, 'kind'> & { multiplier?: number | null; option?: { multiplier?: number | string | null } | null },
): number {
  const sign = SIGN[row.action]
  const price = Number(row.price)
  const qty = Number(row.quantity)
  const multiplier =
    instrument.kind === 'option' && instrument.option?.multiplier != null
      ? Number(instrument.option.multiplier)
      : 1
  const commission = Number(row.commission ?? 0)
  const fees = Number(row.fees ?? 0)
  return sign * price * qty * multiplier - commission - fees
}

export function isValidActionForKind(
  action: TradeAction,
  kind: Instrument['kind'],
): boolean {
  if (action === 'buy' || action === 'sell') return kind !== 'option'
  return kind === 'option'
}
