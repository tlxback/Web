<template>
  <main class="forum">
    <section class="hero">
      <div>
        <h1>论坛</h1>
        <p>分享想法，交流经验，友善讨论。</p>
      </div>
      <button class="primary" @click="showComposer = !showComposer">
        {{ showComposer ? '收起发帖' : '发布新帖' }}
      </button>
    </section>

    <section v-if="showComposer" class="card composer">
      <h2>发布新帖</h2>
      <input v-model="draft.title" maxlength="200" placeholder="帖子标题" />
      <textarea v-model="draft.content_html" rows="8"
        placeholder="支持 HTML（例如 &lt;strong&gt;重点&lt;/strong&gt;、&lt;img src=&quot;...&quot;&gt;）"></textarea>
      <div class="toolbar">
        <input type="file" accept="image/*,video/*" @change="uploadMedia" />
        <button class="secondary" @click="preview = !preview">{{ preview ? '编辑' : '预览' }}</button>
        <button class="primary" :disabled="saving" @click="submitPost">{{ saving ? '发布中…' : '发布' }}</button>
      </div>
      <div v-if="lastMediaUrl" class="media-link">上传链接：<code>{{ lastMediaUrl }}</code> <button class="secondary" @click="copyMediaUrl">复制链接</button></div>
      <div v-if="preview" class="preview content" v-html="draft.content_html"></div>
      <pre v-if="draft.content_html" class="html-highlight"><code class="language-html">{{ draft.content_html }}</code></pre>
      <p v-if="message" class="message">{{ message }}</p>
    </section>

    <section class="card">
      <div class="section-title"><h2>最新帖子</h2><button class="secondary" @click="loadPosts">刷新</button></div>
      <p v-if="loading">加载中…</p>
      <p v-else-if="!posts.length" class="muted">还没有帖子，来发布第一篇吧。</p>
      <article v-for="post in posts" :key="post.id" class="post-row">
        <div>
          <RouterLink :to="`/posts/${post.id}`" class="post-title">{{ post.title }}</RouterLink>
          <div class="excerpt content" v-html="post.content_html"></div>
          <small>作者：<RouterLink :to="`/profile?uname=${encodeURIComponent(post.author)}`">{{ post.author }}</RouterLink> · {{ formatDate(post.created_at) }}</small>
        </div>
        <RouterLink :to="`/posts/${post.id}`" class="read-more">查看 →</RouterLink>
      </article>
    </section>
  </main>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const posts = ref([])
const loading = ref(false)
const saving = ref(false)
const showComposer = ref(false)
const preview = ref(false)
const message = ref('')
const draft = reactive({ title: '', content_html: '' })
const lastMediaUrl = ref('')

const tokenHeaders = () => ({ Authorization: 'Bearer ' + (localStorage.getItem('access_token') || '') })
const formatDate = value => value ? new Date(value).toLocaleString() : ''

async function highlightHtml () {
  await nextTick()
  const code = document.querySelector('.html-highlight code')
  if (code && window.hljs) window.hljs.highlightElement(code)
}
watch(() => draft.content_html, highlightHtml)

async function loadPosts () {
  loading.value = true
  try {
    const res = await fetch('/api/posts')
    if (!res.ok) throw new Error()
    posts.value = await res.json()
  } catch {
    message.value = '帖子加载失败，请稍后重试'
  } finally { loading.value = false }
}

async function uploadMedia (event) {
  const file = event.target.files?.[0]
  if (!file) return
  const body = new FormData()
  body.append('media', file)
  try {
    const res = await fetch('/api/private/upload-media', { method: 'POST', headers: tokenHeaders(), body })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '上传失败')
    const tag = data.type === 'video'
      ? `<video controls src="${data.url}"></video>`
      : `<img src="${data.url}" alt="上传的图片">`
    draft.content_html += `\n${tag}\n`
    lastMediaUrl.value = data.url
    message.value = '媒体已上传并插入正文'
  } catch (error) { message.value = error.message }
  event.target.value = ''
}

async function copyMediaUrl () {
  if (lastMediaUrl.value) await navigator.clipboard?.writeText(lastMediaUrl.value)
}

async function submitPost () {
  if (!draft.title.trim() || !draft.content_html.trim()) {
    message.value = '请填写标题和正文'
    return
  }
  saving.value = true
  const body = new FormData()
  body.append('title', draft.title)
  body.append('content_html', draft.content_html)
  try {
    const res = await fetch('/api/posts', { method: 'POST', headers: tokenHeaders(), body })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '发布失败')
    draft.title = ''; draft.content_html = ''; showComposer.value = false; message.value = ''
    await loadPosts()
    router.push(`/posts/${data.id}`)
  } catch (error) { message.value = error.message }
  finally { saving.value = false }
}

onMounted(() => { loadPosts(); highlightHtml() })
</script>

<style scoped>
.forum { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.hero, .section-title, .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero { margin-bottom: 22px; } h1 { margin: 0; } h2 { margin: 0 0 14px; }
.hero p, .muted, small { color: #64748b; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 18px; box-shadow: 0 3px 12px #0f172a0a; }
input, textarea { box-sizing: border-box; width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; margin-bottom: 12px; font: inherit; }
textarea { resize: vertical; } button { border: 0; border-radius: 8px; padding: 9px 14px; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; } .primary { background: #2563eb; color: #fff; } .secondary { background: #e2e8f0; color: #1e293b; }
.post-row { display: flex; justify-content: space-between; gap: 16px; padding: 17px 0; border-top: 1px solid #e2e8f0; }
.post-title { color: #1d4ed8; font-size: 1.15rem; font-weight: 700; text-decoration: none; }
.excerpt { max-height: 4.2em; overflow: hidden; margin: 7px 0; } .read-more { white-space: nowrap; color: #2563eb; }
.content :deep(img), .content :deep(video) { max-width: 100%; max-height: 360px; } .preview { border-top: 1px solid #e2e8f0; padding-top: 14px; margin-top: 8px; }
.message { color: #b45309; }
.media-link { margin: 8px 0; color: #475569; }
.html-highlight { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; overflow: auto; text-align: left; }
.html-highlight code { font-family: ui-monospace, monospace; }

</style>
