<template>
  <div class="container mt-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow">
          <div class="card-body">
            <h3 class="card-title mb-3">注册</h3>

            <div v-if="alert" :class="'alert ' + alertClass" role="alert">{{ alert }}</div>

            <form @submit.prevent="onSubmit">
              <div class="mb-3">
                <label class="form-label">用户名</label>
                <input v-model="username" class="form-control" required />
              </div>

              <div class="mb-3">
                <label class="form-label">密码</label>
                <input v-model="password" type="password" class="form-control" required />
              </div>

              <div class="mb-3">
                <label class="form-label">邮箱（可选）</label>
                <input v-model="email" type="email" class="form-control" />
              </div>

              <button class="btn btn-success w-100" :disabled="loading">
                <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                注册
              </button>
            </form>
          </div>
        </div>

        <p class="text-center mt-3">
          <RouterLink to="/login" class="me-2">去登录</RouterLink>
          <RouterLink to="/about">关于</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const email = ref('')
const loading = ref(false)
const alert = ref('')
const alertClass = ref('alert-danger')
const router = useRouter()

async function onSubmit(){
  loading.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams()
    body.append('username', username.value)
    body.append('password', password.value)
    if (email.value) body.append('email', email.value)

    const res = await fetch('/api/public/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    })

    if (!res.ok) {
      const err = await res.json().catch(()=>({detail: '注册失败'}))
      alertClass.value = 'alert-danger'
      alert.value = err.detail || '注册失败'
      return
    }

    alertClass.value = 'alert-success'
    alert.value = '注册成功，正在跳转到登录页'

    setTimeout(()=>router.push('/login'), 800)
  } catch(e){
    alertClass.value = 'alert-danger'
    alert.value = '请求失败'
  } finally {
    loading.value = false
  }
}
</script>
