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

/* ===== macOS 无标题栏适配 =====
   main.cjs 以 hiddenInset 隐藏标题栏后,红绿灯按钮浮于内容左上角:
   主界面整体下移避开按钮,顶部空白条兼作窗口拖动区 */
.platform-mac .home-layout .main-container {
  padding-top: 2.5rem;
}

.platform-mac .home-layout::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 34px;
  -webkit-app-region: drag;
  z-index: 5;
}
</style>
