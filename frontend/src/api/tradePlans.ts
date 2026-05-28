import type { components } from './schema'
import { http } from './http'

export type TradePlan = components['schemas']['TradePlanRead']
export type TradePlanCreate = components['schemas']['TradePlanCreate']

export const tradePlansApi = {
  list: (positionId: string) =>
    http.get(`/api/positions/${positionId}/trade-plans`) as Promise<TradePlan[]>,
  current: (positionId: string) =>
    http.get(`/api/positions/${positionId}/trade-plans/current`) as Promise<TradePlan>,
  byRevision: (positionId: string, revisionNo: number) =>
    http.get(`/api/positions/${positionId}/trade-plans/${revisionNo}`) as Promise<TradePlan>,
  append: (positionId: string, payload: TradePlanCreate) =>
    http.post(`/api/positions/${positionId}/trade-plans`, payload) as Promise<TradePlan>,
}
