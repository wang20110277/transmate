import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import {createPinia} from 'pinia'

let pinia = createPinia()

createApp(App).use(router).use(pinia).use(ElementPlus).mount('#app')