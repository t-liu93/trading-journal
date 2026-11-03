import type { components } from './schema'
import { http } from './http'

export type Instrument = components['schemas']['InstrumentRead']
export type StockCreate = components['schemas']['StockCreate']
export type OptionCreate = components['schemas']['OptionCreate']
export type ForexCreate = components['schemas']['ForexCreate']
export type InstrumentCreate = StockCreate | OptionCreate | ForexCreate
export type InstrumentKind = components['schemas']['InstrumentKind']

export interface InstrumentCreateResult {
  instrument: Instrument
  existed: boolean
}

export interface InstrumentListParams {
  kind?: InstrumentKind
  q?: string
  limit?: number
  offset?: number
  include_expired?: boolean
  option_underlying_id?: string
}

function buildQuery(params?: InstrumentListParams): string {
  if (!params) return ''
  const parts: string[] = []
  if (params.kind) parts.push(`kind=${encodeURIComponent(params.kind)}`)
  if (params.q) parts.push(`q=${encodeURIComponent(params.q)}`)
  if (params.limit) parts.push(`limit=${params.limit}`)
  if (params.offset !== undefined) parts.push(`offset=${params.offset}`)
  if (params.include_expired !== undefined) parts.push(`include_expired=${params.include_expired}`)
  if (params.option_underlying_id) parts.push(`option_underlying_id=${encodeURIComponent(params.option_underlying_id)}`)
  return parts.length > 0 ? `?${parts.join('&')}` : ''
}

export const instrumentsApi = {
  list: (params?: InstrumentListParams) =>
    http.get(`/api/instruments${buildQuery(params)}`) as Promise<Instrument[]>,

  get: (id: string) => http.get(`/api/instruments/${id}`) as Promise<Instrument>,

  create: async (payload: InstrumentCreate): Promise<InstrumentCreateResult> => {
    const { data, status } = await http.postWithStatus<Instrument>('/api/instruments', payload)
    return { instrument: data, existed: status === 200 }
  },
}
