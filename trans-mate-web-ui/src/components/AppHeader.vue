<template>
  <header>
    <div class="header-content">
      <div class="header-left">
        <img src="/icons/logo.svg" alt="虚拟柜员图标" class="logo">
        
        <button type="button" class="header-home-btn" @click="goHome">
          <i class="fas fa-home"></i>
          <span>主页</span>
        </button>
      </div>
      <div class="header-user" ref="headerUserRef">
        <div class="header-user-trigger">
          <span class="header-user-avatar">
            <i class="fas fa-user"></i>
          </span>
          <span class="header-user-name">{{ userName }}</span>
          <i class="fas fa-chevron-down header-user-arrow"></i>
        </div>
        <div class="header-user-actions">
          <button type="button" class="header-menu-btn" @click="handlePersonalCenter">
            <i class="fas fa-user-circle"></i>
            <span>个人中心</span>
          </button>
          <button type="button" class="header-logout-btn" @click="handleLogout">
            <i class="fas fa-sign-out-alt"></i>
            <span>退出登录</span>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, defineEmits, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const props = defineProps<{
  userName: string;
}>();

const emit = defineEmits<{
  (e: 'logout'): void;
}>();

const router = useRouter();
const route = useRoute();
const headerUserRef = ref<HTMLDivElement | null>(null);

const pageTitle = computed(() => {
  if (route.path === '/personal-center') {
    return '个人中心';
  }
  return '虚拟柜员';
});

const handlePersonalCenter = () => {
  router.push('/personal-center');
};

const handleLogout = () => {
  emit('logout');
};

const goHome = () => {
  router.push('/')
}
</script>

<style scoped>
header {
  background: linear-gradient(135deg, #1e40af 0%, #2563eb 50%, #3b82f6 100%);
  color: white;
  padding: 0.875rem 1.25rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  z-index: 100;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  object-fit: contain;
}

.header-home-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  margin-left: 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.header-home-btn:hover {
  opacity: 0.8;
}

.header-content h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.header-user {
  position: relative;
  display: flex;
  align-items: center;
}

.header-user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 9999px;
  cursor: default;
  transition: background 0.2s ease;
}

.header-user:hover .header-user-trigger {
  background: rgba(255, 255, 255, 0.15);
}

.header-user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
}

.header-user-name {
  font-size: 0.9375rem;
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-user-arrow {
  font-size: 0.625rem;
  opacity: 0.8;
  transition: transform 0.2s ease;
}

.header-user:hover .header-user-arrow {
  transform: rotate(180deg);
}

.header-user-actions {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  min-width: 160px;
  padding: 6px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.1);
  border: 1px solid #e2e8f0;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-6px);
  transition: opacity 0.2s ease, visibility 0.2s ease, transform 0.2s ease;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.header-menu-btn {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.header-menu-btn:hover {
  background: #f0f9ff;
  color: #2563eb;
}

.header-user:hover .header-user-actions {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.header-logout-btn {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.header-logout-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

@media (max-width: 768px) {
  header {
    padding: 0.75rem 1rem;
  }
  .header-content h1 {
    font-size: 1.125rem;
  }
  .header-user-name {
    max-width: 80px;
  }
  .header-home-btn span {
    display: none;
  }
  .header-home-btn {
    padding: 6px;
    margin-left: 8px;
  }
}
</style>
