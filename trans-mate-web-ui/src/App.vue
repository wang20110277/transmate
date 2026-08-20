<template>
  <router-view />
</template>

<script setup lang="ts">
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
