// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../Home.vue'
import AboutView from '../About.vue'

const routes = [
  { path: '/', component: HomeView },       // 访问 / 显示首页
  { path: '/about', component: AboutView }  // 访问 /about 显示关于
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router