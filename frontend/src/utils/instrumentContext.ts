import type { Instrument } from '../api/instruments'

export interface PrimaryInstrumentContext {
  instrument: Instrument | null
  underlyingId: string | null
  loading: boolean
  error: string | null
}

/** Resolve the exact option-underlying ID represented by a Position primary. */
export function getOptionUnderlyingId(instrument: Instrument | null): string | null {
  if (instrument?.kind === 'stock') return instrument.id
  if (instrument?.kind === 'option') return instrument.option?.underlying_id ?? null
  return null
}

export function optionMatchesPrimary(instrument: Instrument, underlyingId: string | null): boolean {
  return instrument.kind !== 'option' || underlyingId === null || instrument.option?.underlying_id === underlyingId
}
