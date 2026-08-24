// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../Home.vue'
import LoginView from '../components/Login.vue'
import RegisterView from '../components/Register.vue'
import AboutView from '../About.vue'
import LogoutView from '../Logout.vue'

const routes = [
  { path: '/', component: HomeView, meta: { requiresAuth: true } },
  { path: '/login', component: LoginView },
  { path: '/register', component: RegisterView },
  { path: '/about', component: AboutView },
  { path: '/logout', component: LogoutView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router