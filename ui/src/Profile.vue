<template>
  <main class="profile page">
    <section class="card">
      <h1>{{ isPublic ? '用户主页' : '个人资料' }}</h1>
      <div v-if="profile" class="identity">
        <img :src="profile.avatar_url" alt="头像" class="avatar" />
        <div><h2>{{ profile.username }}</h2><p>{{ profile.email }}</p><p>注册时间：{{ formatDate(profile.created_at) }}</p></div>
      </div>
      <template v-if="!isPublic">
        <label>更换头像</label>
        <input type="file" accept="image/*" @change="uploadAvatar" />
        <label>自我介绍</label>
        <textarea v-model="bio" maxlength="2000" rows="7" placeholder="介绍一下自己"></textarea>
        <button class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存资料' }}</button>
      </template>
      <p v-if="message" class="message">{{ message }}</p>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const profile = ref(null); const bio = ref(''); const saving = ref(false); const message = ref('')
const isPublic = ref(Boolean(route.query.uname))
const headers = () => ({ Authorization: 'Bearer ' + (localStorage.getItem('access_token') || '') })
const formatDate = value => value ? new Date(value).toLocaleString() : ''
async function load () {
  const endpoint = isPublic.value ? `/api/users/${encodeURIComponent(route.query.uname)}/profile` : '/api/private/profile'
  const options = isPublic.value ? {} : { headers: headers() }
  const res = await fetch(endpoint, options)
  if (res.ok) { profile.value = await res.json(); bio.value = profile.value.bio || '' }
}
async function uploadAvatar (event) {
  const file = event.target.files?.[0]; if (!file) return
  const body = new FormData(); body.append('avatar', file)
  try {
    const res = await fetch('/api/private/upload-avatar', { method: 'POST', headers: headers(), body })
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || '头像上传失败')
    profile.value.avatar_url = `${data.avatar_url}?t=${Date.now()}`; message.value = '头像已更新'
  } catch (error) { message.value = error.message }
  event.target.value = ''
}
async function save () {
  saving.value = true; const body = new FormData(); body.append('bio', bio.value)
  try {
    const res = await fetch('/api/private/profile', { method: 'PATCH', headers: headers(), body })
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || '保存失败')
    profile.value = data; bio.value = data.bio || ''; message.value = '资料已保存'
  } catch (error) { message.value = error.message }
  finally { saving.value = false }
}
onMounted(load)
</script>

<style scoped>
.page { max-width: 760px; margin: 0 auto; padding: 24px 16px; } .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; }
.identity { display: flex; align-items: center; gap: 20px; margin: 20px 0; } .avatar { width: 128px; height: 128px; border-radius: 50%; object-fit: cover; background: #e2e8f0; } h1, h2 { margin-top: 0; } label { display: block; margin: 16px 0 6px; font-weight: 600; }
textarea { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; resize: vertical; } input { margin-bottom: 8px; }
button { border: 0; border-radius: 8px; padding: 10px 16px; cursor: pointer; } .primary { background: #2563eb; color: #fff; } .message { color: #b45309; }
</style>
