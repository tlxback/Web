<template>
  <div class="container mt-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow">
          <div class="card-body">
            <h3 class="card-title mb-3">找回密码</h3>

            <div v-if="alert" :class="'alert ' + alertClass" role="alert">{{ alert }}</div>

            <cap-widget :data-cap-api-endpoint="capApiEndpoint" @solve="onSolve" @error="onError" required></cap-widget>

            <form @submit.prevent="onSubmit">
              <div class="mb-3">
                <label class="form-label">注册邮箱</label>
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

              <div class="mb-3">
                <label class="form-label">新密码</label>
                <input v-model="newPassword" type="password" class="form-control" required />
              </div>

              <div class="mb-3">
                <label class="form-label">确认新密码</label>
                <input v-model="confirmPassword" type="password" class="form-control" required />
              </div>

              <button class="btn btn-primary w-100" :disabled="loading">
                <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                重置密码
              </button>
            </form>
          </div>
        </div>

        <p class="text-center mt-3">
          <RouterLink to="/login" class="me-2">返回登录</RouterLink>
          <RouterLink to="/about">关于</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import '@cap.js/widget'
import { useRouter } from 'vue-router'

const email = ref('')
const verificationCode = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const sendingCode = ref(false)
const loading = ref(false)
const captchaToken = ref('')
const capApiEndpoint = '/api/cap'
const alert = ref('')
const alertClass = ref('alert-danger')
const router = useRouter()

function onSolve(event){ captchaToken.value = event.detail.token }
function onError(){ captchaToken.value = '' }

async function sendCode(){
  if (!email.value) { alertClass.value = 'alert-danger'; alert.value = '请先填写注册邮箱'; return }
  if (!captchaToken.value) { alertClass.value = 'alert-danger'; alert.value = '请先完成人机验证'; return }
  sendingCode.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams({ email: email.value, cap_token: captchaToken.value })
    const res = await fetch('/api/public/send-password-reset-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) { alertClass.value = 'alert-danger'; alert.value = data.detail || '验证码发送失败'; return }
    alertClass.value = 'alert-success'
    alert.value = '验证码已发送，请查收邮件'
  } catch (e) {
    alertClass.value = 'alert-danger'
    alert.value = '请求失败'
  } finally { sendingCode.value = false }
}

async function onSubmit(){
  if (newPassword.value !== confirmPassword.value) {
    alertClass.value = 'alert-danger'
    alert.value = '两次输入的密码不一致'
    return
  }
  if (!captchaToken.value) { alertClass.value = 'alert-danger'; alert.value = '请先完成人机验证'; return }
  loading.value = true
  alert.value = ''
  try {
    const body = new URLSearchParams({
      email: email.value,
      verification_code: verificationCode.value,
      new_password: newPassword.value,
      cap_token: captchaToken.value
    })
    const res = await fetch('/api/public/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) { alertClass.value = 'alert-danger'; alert.value = data.detail || '密码重置失败'; return }
    alertClass.value = 'alert-success'
    alert.value = '密码重置成功，正在跳转到登录页'
    setTimeout(() => router.push('/login'), 800)
  } catch (e) {
    alertClass.value = 'alert-danger'
    alert.value = '请求失败'
  } finally { loading.value = false }
}
</script>
