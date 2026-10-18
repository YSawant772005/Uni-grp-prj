import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { setUnauthorizedHandler } from './services/api/client'
import { useAuthStore } from './stores/auth'
import './styles.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// Refresh failed: the session is gone. Clear it and bounce away from private screens.
setUnauthorizedHandler(() => {
  const auth = useAuthStore(pinia)
  const wasLoaded = auth.loaded
  auth.clearUser()
  if (!wasLoaded) return // the router guard redirects right after ensureLoaded
  const current = router.currentRoute.value
  if (current.matched.some((record) => record.meta.requiresAuth)) {
    void router.replace({ path: '/login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
