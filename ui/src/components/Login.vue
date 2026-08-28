<template>
  <div class="container mt-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow">
          <div class="card-body">
            <h3 class="card-title mb-3">登录</h3>

            <div class="btn-group mb-3" role="group">
              <button type="button" class="btn" :class="loginMode === 'password' ? 'btn-primary' : 'btn-outline-primary'" @click="loginMode = 'password'">密码登录</button>
              <button type="button" class="btn" :class="loginMode === 'code' ? 'btn-primary' : 'btn-outline-primary'" @click="loginMode = 'code'">验证码登录</button>
            </div>

            <div v-if="alert" :class="'alert ' + alertClass" role="alert">{{ alert }}</div>

            <cap-widget :data-cap-api-endpoint="capApiEndpoint" @solve="onSolve" @error="onError" required></cap-widget>

            <form @submit.prevent="onSubmit">
              <template v-if="loginMode === 'password'">
                <div class="mb-3">
                  <label class="form-label">用户名</label>
                  <input v-model="username" class="form-control" required />
                </div>
                <div class="mb-3">
                  <label class="form-label">密码</label>
                  <input v-model="password" type="password" class="form-control" required />
                </div>
              </template>
              <template v-else>
                <div class="mb-3">
                  <label class="form-label">注册邮箱</label>
                  <div class="input-group">
                    <input v-model="email" type="email" class="form-control" required />
                    <button type="button" class="btn btn-outline-secondary" @click="sendLoginCode" :disabled="sendingCode">{{ sendingCode ? '发送中...' : '发送验证码' }}</button>
                  </div>
                </div>
                <div class="mb-3">
                  <label class="form-label">邮箱验证码</label>
                  <input v-model="verificationCode" class="form-control" inputmode="numeric" maxlength="6" required />
                </div>
              </template>

              <button class="btn btn-primary w-100" :disabled="loading">
                <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                登录
              </button>
            </form>
          </div>
        </div>

        <p class="text-center mt-3">
          <RouterLink to="/register" class="me-2">去注册</RouterLink>
          <RouterLink to="/forgot-password" class="me-2">忘记密码</RouterLink>
          <RouterLink to="/about">关于</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import '@cap.js/widget'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const email = ref('')
const verificationCode = ref('')
const loginMode = ref('password')
const sendingCode = ref(false)
const loading = ref(false)
const captchaToken = ref('')
const capApiEndpoint = '/api/cap'
const alert = ref('')
const alertClass = ref('alert-danger')
const router = useRouter()

function onSolve(event){ captchaToken.value = event.detail.token }
function onError(){ captchaToken.value = '' }

async function sendLoginCode(){
  if (!email.value) { alertClass.value = 'alert-danger'; alert.value = '请先填写注册邮箱'; return }
  sendingCode.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams({ email: email.value })
    const res = await fetch('/api/public/send-login-code', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString() })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) { alertClass.value = 'alert-danger'; alert.value = data.detail || '验证码发送失败'; return }
    alertClass.value = 'alert-success'; alert.value = '登录验证码已发送，请查收邮件'
  } catch (e) { alertClass.value = 'alert-danger'; alert.value = '请求失败' }
  finally { sendingCode.value = false }
}

async function onSubmit(){
  if (!captchaToken.value) { alertClass.value = 'alert-danger'; alert.value = '请先完成人机验证'; return }
  loading.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams()
    if (loginMode.value === 'password') {
      body.append('username', username.value)
      body.append('password', password.value)
    } else {
      body.append('email', email.value)
      body.append('verification_code', verificationCode.value)
    }
    body.append('cap_token', captchaToken.value)

    const res = await fetch(loginMode.value === 'password' ? '/api/login' : '/api/login/code', {
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
