<template>
  <div class="container mt-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow">
          <div class="card-body">
            <h3 class="card-title mb-3">注册</h3>

            <div v-if="alert" :class="'alert ' + alertClass" role="alert">{{ alert }}</div>

            <cap-widget :data-cap-api-endpoint="capApiEndpoint" @solve="onSolve" @error="onError" required></cap-widget>

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
                <label class="form-label">邮箱</label>
                <div class="input-group">
                  <input v-model="email" type="email" class="form-control" required />
                  <button type="button" class="btn btn-outline-secondary" @click="sendCode" :disabled="sendingCode">
                    {{ sendingCode ? '发送中...' : '发送验证码' }}
                  </button>
                </div>
              </div>

              <div class="mb-3">
                <label class="form-label">邮箱验证码</label>
                <input v-model="verificationCode" class="form-control" inputmode="numeric" maxlength="6" required />
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
import { ref, onMounted } from 'vue'
import '@cap.js/widget'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const email = ref('')
const verificationCode = ref('')
const loading = ref(false)
const captchaToken = ref('')
const capApiEndpoint = '/api/cap/challenge'
const sendingCode = ref(false)
const alert = ref('')
const alertClass = ref('alert-danger')
const router = useRouter()

async function sendCode(){
  if (!email.value) {
    alertClass.value = 'alert-danger'
    alert.value = '请先填写邮箱'
    return
  }
  sendingCode.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams({ email: email.value })
    const res = await fetch('/api/public/send-verification-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      alertClass.value = 'alert-danger'
      alert.value = data.detail || '验证码发送失败'
      return
    }
    alertClass.value = 'alert-success'
    alert.value = '验证码已发送，请查收邮件'
  } catch(e){
    alertClass.value = 'alert-danger'
    alert.value = '请求失败'
  } finally {
    sendingCode.value = false
  }
}

function onSolve(event){ captchaToken.value = event.detail.token }
function onError(){ captchaToken.value = '' }

async function onSubmit(){
  if (!captchaToken.value) { alertClass.value = 'alert-danger'; alert.value = '请先完成人机验证'; return }
  loading.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams()
    body.append('username', username.value)
    body.append('password', password.value)
    body.append('email', email.value)
    body.append('verification_code', verificationCode.value)
    body.append('cap_token', captchaToken.value)

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
