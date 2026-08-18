import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// 图标字体本地打包（替代 CDN，桌面端离线可用）
import '@fortawesome/fontawesome-free/css/all.min.css'
// 中文界面字体本地打包（替代 Google Fonts CDN）
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/noto-sans-sc/600.css'
import '@fontsource/noto-sans-sc/700.css'
import App from './App.vue'
import router from './router'
import {createPinia} from 'pinia'

let pinia = createPinia()

// macOS 隐藏标题栏后,红绿灯按钮浮于内容之上;相关让位/拖动样式以该类名启用
if (navigator.userAgent.includes('Mac')) {
  document.documentElement.classList.add('platform-mac')
}

createApp(App).use(router).use(pinia).use(ElementPlus).mount('#app')