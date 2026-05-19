/**
 * Hand-written API types mirroring the backend's Pydantic schemas.
 *
 * Kept tiny on purpose — only what F0 actually consumes. From F1 we'll
 * codegen via `openapi-typescript` against `/openapi.json` and delete this.
 */

/** Matches backend `UserRead` (schemas/user.py). */
export interface User {
  id: string
  email: string
  is_active: boolean
  is_verified: boolean
  is_superuser: boolean
  last_login_at: string | null
  created_at: string
}

/** Body of `POST /auth/register` (UserCreate). */
export interface RegisterPayload {
  email: string
  password: string
}

/** Logical body for our login action. Marshalled to the OAuth2 form on the wire. */
export interface LoginPayload {
  email: string
  password: string
}

/**
 * Shape of `detail` returned by fastapi-users for validation-style errors —
 * e.g. `REGISTER_INVALID_PASSWORD`. For plain string codes (`LOGIN_BAD_CREDENTIALS`,
 * `REGISTER_USER_ALREADY_EXISTS`) the `detail` is just a string.
 */
export interface ApiErrorDetailObject {
  code: string
  reason: string
}

export type ApiErrorDetail = string | ApiErrorDetailObject | unknown

/**
 * Error thrown by the HTTP client for any non-2xx response.
 *
 * `status` is the HTTP status; `detail` is the parsed `detail` field from the
 * response body when present (string code or `{code, reason}` object), or the
 * raw body otherwise. `message` is a best-effort human-readable string suitable
 * for direct surfacing in a toast.
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: ApiErrorDetail

  constructor(status: number, detail: ApiErrorDetail, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}
