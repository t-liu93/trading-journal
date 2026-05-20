/**
 * Auth store: holds the currently-logged-in user and exposes the actions that
 * change that state (register / login / logout / fetchMe / init).
 *
 * Cookies are stored by the browser, not here — this store is the in-memory
 * mirror of "is there a valid session and who does it belong to?".
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { http } from '../api/http'
import { ApiError, type LoginPayload, type RegisterPayload, type User } from '../api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  /** True after `init()` has resolved, regardless of whether a session existed. */
  const initialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  /**
   * Refresh `user` from `/api/users/me`. A 401 is the normal "no active
   * session" response and is silently swallowed; any other error is re-thrown.
   */
  async function fetchMe(): Promise<void> {
    try {
      user.value = (await http.get('/api/users/me')) as User
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        user.value = null
        return
      }
      throw err
    }
  }

  async function register(payload: RegisterPayload): Promise<void> {
    await http.post('/api/auth/register', payload)
  }

  /**
   * `/api/auth/login` uses `OAuth2PasswordRequestForm` — the wire format is
   * form-urlencoded with `username` (= email) and `password`. We expose the
   * caller-friendly `{email, password}` shape and marshal here.
   */
  async function login(payload: LoginPayload): Promise<void> {
    await http.postForm('/api/auth/login', {
      username: payload.email,
      password: payload.password,
    })
    await fetchMe()
  }

  /**
   * Clears the local session. A 401 means the server-side session is already
   * gone — the local mirror must still be cleared, so we swallow it. Any other
   * error (network / 5xx) leaves `user` intact and is re-thrown so the caller
   * can surface it; the server session may still be valid in that case.
   */
  async function logout(): Promise<void> {
    try {
      await http.post('/api/auth/logout')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        user.value = null
        return
      }
      throw err
    }
    user.value = null
  }

  /**
   * Called once at app bootstrap (before `router.isReady()`) to seed `user`
   * from any existing cookie. Subsequent calls are no-ops.
   *
   * MUST NOT throw: it's awaited in `main.ts` *before* `app.mount()`, so an
   * unhandled rejection here means the app never mounts (blank page). If the
   * backend is unreachable at bootstrap (502 / network error), we degrade to
   * "no session" — the app still mounts and lands on /login; the user re-auths
   * once the backend is back. A 401 is already handled inside `fetchMe`.
   */
  async function init(): Promise<void> {
    if (initialized.value) return
    try {
      await fetchMe()
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  return {
    // state
    user,
    initialized,
    // getters
    isAuthenticated,
    // actions
    register,
    login,
    logout,
    fetchMe,
    init,
  }
})
