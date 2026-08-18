<template>
  <header>
    <div class="header-content">
      <div class="header-left">
        <img src="/icons/logo.svg" alt="虚拟柜员图标" class="logo">
        <span class="header-title">欢迎使用 TransMate 智能助手</span>
      </div>
      <div class="header-right">
        <button type="button" class="header-home-btn" @click="goHome">
          <i class="fas fa-home"></i>
          <span>主页</span>
        </button>
        <div class="header-user">
          <span class="header-user-avatar">
            <i class="fas fa-user"></i>
          </span>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();

const goHome = () => {
  router.push('/')
}
</script>

<style scoped>
header {
  background: var(--color-surface, #ffffff);
  color: #1e293b;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
  z-index: 100;
}

/* macOS 无标题栏:顶栏兼作窗口拖动区,左侧为红绿灯按钮留白 */
.platform-mac header {
  -webkit-app-region: drag;
  padding-left: 6rem;
}

.platform-mac .header-right {
  -webkit-app-region: no-drag;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1600px;
  margin: 0 auto;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo {
  width: 38px;
  height: 38px;
  object-fit: contain;
}

.header-title {
  font-size: 1.0625rem;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: 0.5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-home-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.25);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s;
}

.header-home-btn:hover {
  background: rgba(37, 99, 235, 0.15);
}

.header-user {
  display: flex;
  align-items: center;
}

.header-user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  font-size: 0.9375rem;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-radius: 50%;
  cursor: pointer;
}
</style>
