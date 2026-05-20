import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Naive UI's recommended font stack (Lato for UI, Fira Code for monospace).
import 'vfonts/Lato.css'
import 'vfonts/FiraCode.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
app.use(createPinia())

// CRITICAL ORDERING:
//
// Vue Router's `app.use(router)` *immediately* kicks off the initial navigation
// (it calls `router.push(location)` inside install — see vue-router source). The
// `beforeEach` guard runs as part of that initial navigation. So the guard
// would otherwise observe `user === null` and bounce a logged-in reload to
// `/login`, EVEN IF `/api/users/me` would have succeeded — the request just
// completes after the guard has already decided.
//
// We therefore seed the auth store from the existing cookie BEFORE installing
// the router. Then the guard fires with the correct state on its very first
// run.
const auth = useAuthStore()
await auth.init()

app.use(router)

// Dev-only: hang the store off `window.__auth` for DevTools console driving.
// Tree-shaken in production because `import.meta.env.DEV` is a build-time constant.
if (import.meta.env.DEV) {
  ;(window as unknown as { __auth: typeof auth }).__auth = auth
}

await router.isReady()
app.mount('#app')
