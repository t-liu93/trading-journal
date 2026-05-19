import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Naive UI's recommended font stack (Lato for UI, Fira Code for monospace).
import 'vfonts/Lato.css'
import 'vfonts/FiraCode.css'
import './style.css'
import App from './App.vue'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
app.use(createPinia())

// Dev-only: hang the auth store off `window.__auth` so F0.2 verification
// (and later quick debugging) can drive it from the DevTools console.
// Tree-shaken out of production builds because `import.meta.env.DEV` is a
// build-time constant.
if (import.meta.env.DEV) {
  const authStore = useAuthStore()
  ;(window as unknown as { __auth: typeof authStore }).__auth = authStore
}

app.mount('#app')
