<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <h2>🏠 首页</h2>
      <button @click="goLogout" style="padding:6px 10px;border-radius:4px;border:1px solid #ccc;background:#fff;cursor:pointer">登出</button>
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
</script>