import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import Home from '../views/Home.vue'
import About from '../views/About.vue'
import PersonalCenter from '../views/PersonalCenter.vue'
import Login from '../views/Login.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home, meta: { requiresAuth: true } },
    { path: '/login', name: 'login', component: Login, meta: { guestOnly: true } },
    { path: '/about', name: 'about', component: About },
    { path: '/personal-center', name: 'personal-center', component: PersonalCenter, meta: { requiresAuth: true } },
  ],
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const token = localStorage.getItem('token')

  // 如果本地有token但没有用户信息，尝试获取用户信息
  if (token && !userStore.isLoggedIn) {
    const success = await userStore.fetchUserInfo()
    if (!success) {
      // 获取失败，清除token并跳转到登录页
      userStore.clearAuth()
      if (to.meta.requiresAuth) {
        return next('/login')
      }
    }
  }

  // 需要登录的页面
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return next('/login')
  }

  // 游客专用页面（如登录页）
  if (to.meta.guestOnly && userStore.isLoggedIn) {
    return next('/')
  }

  next()
})

export default router
