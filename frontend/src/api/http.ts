/**
 * Thin `fetch` wrapper for talking to the backend.
 *
 * Conventions:
 *   - Same-origin requests (the dev-time Vite proxy and the prod single-container
 *     deployment both ensure this) — but we still pass `credentials: 'include'`
 *     so cookies flow consistently across environments.
 *   - 2xx with JSON body → returns parsed JSON
 *   - 204 No Content → returns `null`
 *   - Non-2xx → throws `ApiError` with a normalised `message` and the raw `detail`.
 *
 * Two body encodings:
 *   - JSON (default) — `Content-Type: application/json` — for `/auth/register`,
 *     `/accounts`, `/users/me` PATCH, etc.
 *   - Form-urlencoded — for `/auth/login` (FastAPI Users uses
 *     `OAuth2PasswordRequestForm` which only accepts form bodies).
 */

import { ApiError, type ApiErrorDetail } from './types'

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

interface RequestOptions {
  body?: unknown
  bodyType?: 'json' | 'form'
  headers?: Record<string, string>
}

function deriveMessage(detail: ApiErrorDetail, status: number): string {
  if (typeof detail === 'string' && detail.length > 0) return detail

  if (
    detail !== null &&
    typeof detail === 'object' &&
    !Array.isArray(detail) &&
    'reason' in detail &&
    typeof (detail as { reason: unknown }).reason === 'string'
  ) {
    return (detail as { reason: string }).reason
  }

  // FastAPI/Pydantic validation error: detail is an array of
  // { loc: [...], msg: string, ... }. Show the first error, prefixed with the
  // field path (loc[0] is "body"/"query" — drop it).
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown; loc?: unknown } | undefined
    if (first && typeof first.msg === 'string') {
      const loc = Array.isArray(first.loc) ? first.loc.slice(1).join('.') : ''
      return loc ? `${loc}: ${first.msg}` : first.msg
    }
  }

  return `HTTP ${status}`
}

async function request(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<unknown> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) }
  let body: BodyInit | undefined

  if (options.body !== undefined && options.body !== null) {
    if (options.bodyType === 'form') {
      const params = new URLSearchParams()
      for (const [k, v] of Object.entries(options.body as Record<string, string>)) {
        params.set(k, v)
      }
      body = params
      headers['Content-Type'] = 'application/x-www-form-urlencoded'
    } else {
      body = JSON.stringify(options.body)
      headers['Content-Type'] = 'application/json'
    }
  }

  const response = await fetch(path, {
    method,
    headers,
    body,
    credentials: 'include',
  })

  if (response.status === 204) return null

  const contentType = response.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json')
  const parsed: unknown = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    const detail: ApiErrorDetail =
      isJson && parsed !== null && typeof parsed === 'object' && 'detail' in parsed
        ? (parsed as { detail: ApiErrorDetail }).detail
        : parsed
    throw new ApiError(response.status, detail, deriveMessage(detail, response.status))
  }

  return parsed
}

export const http = {
  get: (path: string) => request('GET', path),
  post: (path: string, body?: unknown) => request('POST', path, { body }),
  postForm: (path: string, body: Record<string, string>) =>
    request('POST', path, { body, bodyType: 'form' }),
  patch: (path: string, body?: unknown) => request('PATCH', path, { body }),
  delete: (path: string) => request('DELETE', path),
}
