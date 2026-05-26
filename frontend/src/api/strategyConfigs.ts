import type { components } from './schema'
import { http } from './http'

export type StrategyConfig = components['schemas']['StrategyConfigRead']
export type StrategyConfigCreate = components['schemas']['StrategyConfigCreate']
export type StrategyConfigUpdate = components['schemas']['StrategyConfigUpdate']
export type StrategyType = components['schemas']['StrategyType']

export const strategyConfigsApi = {
  list: () => http.get('/api/strategy-configs') as Promise<StrategyConfig[]>,

  get: (type: StrategyType) =>
    http.get(`/api/strategy-configs/${type}`) as Promise<StrategyConfig>,

  upsert: (payload: StrategyConfigCreate) =>
    http.post('/api/strategy-configs', payload) as Promise<StrategyConfig>,

  update: (type: StrategyType, payload: StrategyConfigUpdate) =>
    http.patch(`/api/strategy-configs/${type}`, payload) as Promise<StrategyConfig>,

  remove: (type: StrategyType) =>
    http.delete(`/api/strategy-configs/${type}`) as Promise<null>,
}
