// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../components/Login.vue'
import AboutView from '../About.vue'

const routes = [
  { path: '/', component: LoginView },       // 根路由显示登录页
  { path: '/about', component: AboutView }  // 访问 /about 显示关于
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router