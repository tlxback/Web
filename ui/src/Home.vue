<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <h2>🏠 首页</h2>
      <div>
        <button @click="goLogout" style="padding:6px 10px;border-radius:4px;border:1px solid #ccc;background:#fff;cursor:pointer">登出</button>
        <button @click="deleteAccount" style="padding:6px 10px;margin-left:8px;border-radius:4px;border:1px solid #dc3545;background:#fff;color:#dc3545;cursor:pointer">注销账号</button>
      </div>
    </div>
    <p>这是首页内容，数据保留完好</p>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
function goLogout() {
  router.push('/logout')
}

async function deleteAccount() {
  if (!window.confirm('注销账号后数据将被永久删除，确定继续吗？')) return

  const token = localStorage.getItem('access_token')
  if (!token) {
    router.replace('/login')
    return
  }

  try {
    const res = await fetch('/api/private/account', {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + token }
    })
    if (!res.ok) {
      const error = await res.json().catch(() => ({}))
      window.alert(error.detail || '注销账号失败')
      return
    }
    localStorage.removeItem('access_token')
    document.cookie = 'access_token=; Max-Age=0; path=/;'
    router.replace('/login')
  } catch (e) {
    window.alert('请求失败，请稍后重试')
  }
}
</script>