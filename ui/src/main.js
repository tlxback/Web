import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Navigation guard: the bearer token is kept in localStorage.
router.beforeEach(async (to, from, next) => {
  if (to.meta && to.meta.requiresAuth) {
    const token = localStorage.getItem('access_token')
    if (!token) return next('/login')
    try {
      const res = await fetch('/api/private/users/me', {
        headers: { 'Authorization': 'Bearer ' + token }
      })
      if (res.ok) return next()
    } catch (e) {
      // ignore
    }
    return next('/login')
  }
  return next()
})

const app = createApp(App)
app.use(router)
app.mount('#app')