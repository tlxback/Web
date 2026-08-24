<template>
  <div>
    <h2>正在退出...</h2>
    <p>若未自动跳转，请稍候或手动返回登录页。</p>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

function clearAuth() {
  try {
    // remove access token from localStorage
    localStorage.removeItem('access_token')
    // clear common cookies (access_token / refresh_token)
    document.cookie = 'access_token=; Max-Age=0; path=/;'
    document.cookie = 'refresh_token=; Max-Age=0; path=/;'
  } catch (e) {
    // ignore
  }
}

onMounted(async () => {
  // attempt server-side logout if endpoint exists
  try {
    await fetch('/api/logout', { method: 'POST', credentials: 'include' })
  } catch (e) {
    // ignore network errors
  }
  clearAuth()
  // small delay so user sees message briefly
  setTimeout(() => {
    router.replace('/login')
  }, 300)
})
</script>
