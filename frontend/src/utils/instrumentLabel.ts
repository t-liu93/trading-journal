import type { Instrument } from '../api/instruments'

/**
 * Compact instrument code for display.
 * - Option: "AAPL225.50P260604" = <symbol><strike.2><P|C><expiry YYMMDD>
 * - Stock / forex: the bare symbol, e.g. "AAPL", "EURUSD".
 */
export function formatInstrumentCode(inst: Instrument): string {
  if (inst.kind !== 'option' || !inst.option) return inst.symbol
  const o = inst.option
  const typeLetter = o.opt_type === 'call' ? 'C' : 'P'
  const strike = Number(o.strike).toFixed(2)
  // expiry is an ISO date string "YYYY-MM-DD"; parse parts directly so the
  // shown date never shifts by a day from new Date() timezone conversion.
  const [yyyy = '', mm = '', dd = ''] = String(o.expiry).slice(0, 10).split('-')
  const yy = yyyy.slice(-2)
  return `${inst.symbol}${strike}${typeLetter}${yy}${mm}${dd}`
}
