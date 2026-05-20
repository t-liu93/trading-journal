/**
 * Account REST API client.
 *
 * Thin typed wrapper around the backend's ``/api/accounts`` endpoints (Phase 4).
 * Types come straight from the auto-generated OpenAPI schema, so a backend
 * field rename / addition is a compile-time error after a single
 * ``npm run codegen``.
 *
 * No view code reaches into ``http.ts`` directly for Account operations — they
 * all go through here, which makes mocking and refactoring easier later.
 */

import { http } from './http'
import type { components } from './schema'

export type Account = components['schemas']['AccountRead']
export type AccountCreate = components['schemas']['AccountCreate']
export type AccountUpdate = components['schemas']['AccountUpdate']
export type AccountType = components['schemas']['AccountType']

export const accountsApi = {
  /** ``GET /accounts``. Pass ``true`` to include soft-deleted (archived) rows. */
  list: (includeArchived = false) =>
    http.get(`/api/accounts?include_archived=${includeArchived}`) as Promise<Account[]>,

  /** ``GET /accounts/{id}``. Throws ``ApiError`` with status 404 if missing or not owned. */
  get: (id: string) => http.get(`/api/accounts/${id}`) as Promise<Account>,

  /** ``POST /accounts``. ``user_id`` is derived from the session cookie server-side. */
  create: (payload: AccountCreate) => http.post('/api/accounts', payload) as Promise<Account>,

  /** ``PATCH /accounts/{id}``. Partial update; omit fields you don't want to change. */
  update: (id: string, payload: AccountUpdate) =>
    http.patch(`/api/accounts/${id}`, payload) as Promise<Account>,

  /** ``DELETE /accounts/{id}``. Soft-delete (stamps ``archived_at``). Returns ``null`` on 204. */
  remove: (id: string) => http.delete(`/api/accounts/${id}`) as Promise<null>,
}
