// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../Home.vue'
import LoginView from '../components/Login.vue'
import RegisterView from '../components/Register.vue'
import ForgotPasswordView from '../components/ForgotPassword.vue'
import AboutView from '../About.vue'
import LogoutView from '../Logout.vue'
import PostDetailView from '../PostDetail.vue'
import ProfileView from '../Profile.vue'

const routes = [
  { path: '/', component: HomeView, meta: { requiresAuth: true } },
  { path: '/login', component: LoginView },
  { path: '/register', component: RegisterView },
  { path: '/forgot-password', component: ForgotPasswordView },
  { path: '/about', component: AboutView },
  { path: '/logout', component: LogoutView },
  { path: '/posts/:id', component: PostDetailView, meta: { requiresAuth: true } },
  { path: '/profile', component: ProfileView, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router