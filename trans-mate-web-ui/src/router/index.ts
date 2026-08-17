import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import About from '../views/About.vue'
import PersonalCenter from '../views/PersonalCenter.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/login', redirect: '/' },
    { path: '/about', name: 'about', component: About },
    { path: '/personal-center', name: 'personal-center', component: PersonalCenter },
  ],
})

export default router
