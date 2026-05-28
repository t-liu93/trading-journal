/**
 * Vue Router setup with an auth guard.
 *
 * Guard behaviour:
 *   - Navigating to a route that requires auth without a session → /login
 *   - Navigating to /login or /register while already authenticated → /
 *
 * The guard reads `useAuthStore()` synchronously, which assumes the store has
 * already been seeded by `await authStore.init()` in `main.ts` BEFORE
 * `router.isReady()`. Without that, the very first navigation runs with
 * `user === null` and the user sees a `/login → /` flicker after a page
 * reload while logged in.
 */

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('../views/AccountsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/positions',
    name: 'positions',
    component: () => import('../views/PositionsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/positions/:id',
    name: 'position-detail',
    component: () => import('../views/PositionDetailView.vue'),
    meta: { requiresAuth: true },
    props: true,
  },
  {
    path: '/instruments',
    name: 'instruments',
    component: () => import('../views/InstrumentsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings/strategies',
    name: 'settings-strategies',
    component: () => import('../views/SettingsStrategiesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/RegisterView.vue'),
  },
  // Catch-all → dashboard (which the guard will then redirect to /login if needed).
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const isGuestRoute = to.name === 'login' || to.name === 'register'

  if (!isGuestRoute && to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (isGuestRoute && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
