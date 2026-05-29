import type { components } from './schema'
import { http } from './http'

export type DashboardSummary    = components['schemas']['DashboardSummary']
export type ClosedSummary       = components['schemas']['ClosedSummary']
export type OpenSummary         = components['schemas']['OpenSummary']
export type CurrencyAmount      = components['schemas']['CurrencyAmount']
export type MonthCurrencyAmount = components['schemas']['MonthCurrencyAmount']

export const dashboardApi = {
  summary: () => http.get('/api/dashboard/summary') as Promise<DashboardSummary>,
}
