import { createRouter, createWebHashHistory } from 'vue-router'
import Home from '../views/Home.vue'
import About from '../views/About.vue'
import PersonalCenter from '../views/PersonalCenter.vue'

const router = createRouter({
  // hash 模式：Electron 打包后以 file:// 加载，history 模式在该协议下不工作
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/login', redirect: '/' },
    { path: '/about', name: 'about', component: About },
    { path: '/personal-center', name: 'personal-center', component: PersonalCenter },
  ],
})

export default router
