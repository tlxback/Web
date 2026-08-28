<template>
  <main class="page">
    <RouterLink to="/">← 返回论坛</RouterLink>
    <p v-if="loading">加载中…</p>
    <section v-else-if="post" class="card">
      <h1>{{ post.title }}</h1>
      <small>作者：<RouterLink :to="`/profile?uname=${encodeURIComponent(post.author)}`">{{ post.author }}</RouterLink> · {{ formatDate(post.created_at) }}</small>
      <div class="content post-content" v-html="post.content_html"></div>
      <hr />
      <h2>回复（{{ post.replies.length }}）</h2>
      <article v-for="reply in post.replies" :key="reply.id" class="reply">
        <div class="content" v-html="reply.content_html"></div>
        <small><RouterLink :to="`/profile?uname=${encodeURIComponent(reply.author)}`">{{ reply.author }}</RouterLink> · {{ formatDate(reply.created_at) }}</small>
      </article>
      <form @submit.prevent="submitReply">
        <textarea v-model="replyText" rows="5" placeholder="写下你的回复（支持 HTML）"></textarea>
        <div class="toolbar">
          <input type="file" accept="image/*,video/*" @change="uploadMedia" />
          <button class="primary" :disabled="sending">{{ sending ? '发送中…' : '回复' }}</button>
        </div>
      </form>
      <p v-if="lastMediaUrl" class="media-link">上传链接：<code>{{ lastMediaUrl }}</code></p>
      <pre v-if="replyText" class="html-highlight"><code class="language-html">{{ replyText }}</code></pre>
      <p v-if="message" class="message">{{ message }}</p>
    </section>
    <p v-else>帖子不存在。</p>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const post = ref(null)
const loading = ref(true)
const sending = ref(false)
const replyText = ref('')
const message = ref('')
const lastMediaUrl = ref('')
const tokenHeaders = () => ({ Authorization: 'Bearer ' + (localStorage.getItem('access_token') || '') })
const formatDate = value => value ? new Date(value).toLocaleString() : ''

async function load () {
  try {
    const res = await fetch(`/api/posts/${route.params.id}`)
    if (res.ok) post.value = await res.json()
  } finally { loading.value = false }
}
async function uploadMedia (event) {
  const file = event.target.files?.[0]
  if (!file) return
  const body = new FormData(); body.append('media', file)
  try {
    const res = await fetch('/api/private/upload-media', { method: 'POST', headers: tokenHeaders(), body })
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || '上传失败')
    replyText.value += `\n${data.type === 'video' ? `<video controls src="${data.url}"></video>` : `<img src="${data.url}" alt="上传的图片">`}\n`
    lastMediaUrl.value = data.url
  } catch (error) { message.value = error.message }
  event.target.value = ''
}
async function submitReply () {
  if (!replyText.value.trim()) { message.value = '请输入回复内容'; return }
  sending.value = true
  const body = new FormData(); body.append('content_html', replyText.value)
  try {
    const res = await fetch(`/api/posts/${route.params.id}/replies`, { method: 'POST', headers: tokenHeaders(), body })
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || '回复失败')
    post.value.replies.push(data); replyText.value = ''; message.value = ''
  } catch (error) { message.value = error.message }
  finally { sending.value = false }
}
onMounted(load)
</script>

<style scoped>
.page { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.card { margin-top: 18px; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 22px; }
h1 { margin: 0 0 6px; } h2 { margin-top: 22px; } small { color: #64748b; }
.content :deep(img), .content :deep(video) { max-width: 100%; max-height: 520px; } .post-content { margin: 22px 0; line-height: 1.7; }
hr { border: 0; border-top: 1px solid #e2e8f0; } .reply { border-top: 1px solid #e2e8f0; padding: 14px 0; }
textarea { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; resize: vertical; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 10px; } button { border: 0; border-radius: 8px; padding: 9px 14px; cursor: pointer; } .primary { background: #2563eb; color: #fff; }
.message { color: #b45309; }
.media-link { color: #475569; }
.html-highlight { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; overflow: auto; text-align: left; }
.html-highlight code { font-family: ui-monospace, monospace; }

.media-link { color: #475569; }

</style>
