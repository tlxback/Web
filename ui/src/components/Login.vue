<template>
  <div class="container mt-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow">
          <div class="card-body">
            <h3 class="card-title mb-3">登录</h3>

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

              <button class="btn btn-primary w-100" :disabled="loading">
                <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                登录
              </button>
            </form>
          </div>
        </div>

        <p class="text-center mt-3"><RouterLink to="/about">关于</RouterLink></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
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

    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    })

    if (!res.ok) {
      const err = await res.json().catch(()=>({detail: '登录失败'}))
      alertClass.value = 'alert-danger'
      alert.value = err.detail || '登录失败'
      return
    }

    const data = await res.json()
    localStorage.setItem('access_token', data.access_token)
    alertClass.value = 'alert-success'
    alert.value = '登录成功'

    // 简单重定向到 about 页面或保留在首页
    setTimeout(()=>router.push('/about'), 500)
  } catch(e){
    alertClass.value = 'alert-danger'
    alert.value = '请求失败'
  } finally {
    loading.value = false
  }
}
</script>
