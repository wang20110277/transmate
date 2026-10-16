<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

// 根组件统一恢复登录态。
// 子组件的 onMounted 先于父组件执行，且非首页路由不会经过 Home.vue，
// 若只在那里恢复，直接落到 /#/settings 时 userInfo 恒为 null，
// isLoggedIn 也就恒为 false（技能/模型面板会误判成未登录）。
const userStore = useUserStore()

onMounted(async () => {
  userStore.initFromStorage()
  if (userStore.token && !userStore.userInfo) {
    await userStore.fetchUserInfo()
  }
})
</script>

<style>
#app {
  height: 100vh;
  font-family: "Noto Sans SC", "Helvetica Neue", Arial, sans-serif;
}

/* macOS 无标题栏适配由各页面自行处理:
   Home.vue 在侧栏顶部预留红绿灯拖动区(见 .sidebar-top),
   避免全局遮罩式拖动条遮挡顶部按钮点击 */
</style>
