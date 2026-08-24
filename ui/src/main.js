import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// helper to read cookie by name
function getCookie(name) {
  const v = `; ${document.cookie}`
  const parts = v.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
}

// navigation guard: if route requiresAuth, check cookie token and validate with backend
router.beforeEach(async (to, from, next) => {
  if (to.meta && to.meta.requiresAuth) {
    const token = getCookie('access_token') || localStorage.getItem('access_token')
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