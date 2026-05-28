import type { components } from './schema'
import { http } from './http'

export type WheelMeta = components['schemas']['WheelMetaRead']
export type WheelMetaCreate = components['schemas']['WheelMetaCreate']
export type WheelMetaUpdate = components['schemas']['WheelMetaUpdate']

export type PmccMeta = components['schemas']['PmccMetaRead']
export type PmccMetaCreate = components['schemas']['PmccMetaCreate']
export type PmccMetaUpdate = components['schemas']['PmccMetaUpdate']

export const wheelMetaApi = {
  get: (pid: string) => http.get(`/api/positions/${pid}/wheel-meta`) as Promise<WheelMeta>,
  create: (pid: string, payload: WheelMetaCreate) =>
    http.post(`/api/positions/${pid}/wheel-meta`, payload) as Promise<WheelMeta>,
  update: (pid: string, payload: WheelMetaUpdate) =>
    http.patch(`/api/positions/${pid}/wheel-meta`, payload) as Promise<WheelMeta>,
  remove: (pid: string) => http.delete(`/api/positions/${pid}/wheel-meta`) as Promise<null>,
}

export const pmccMetaApi = {
  get: (pid: string) => http.get(`/api/positions/${pid}/pmcc-meta`) as Promise<PmccMeta>,
  create: (pid: string, payload: PmccMetaCreate) =>
    http.post(`/api/positions/${pid}/pmcc-meta`, payload) as Promise<PmccMeta>,
  update: (pid: string, payload: PmccMetaUpdate) =>
    http.patch(`/api/positions/${pid}/pmcc-meta`, payload) as Promise<PmccMeta>,
  remove: (pid: string) => http.delete(`/api/positions/${pid}/pmcc-meta`) as Promise<null>,
}
