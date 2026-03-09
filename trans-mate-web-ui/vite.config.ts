import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), vueJsx()],
  server: {
    port: 3000,
    proxy: {
      '/ws': {
        // target: 'ws://192.168.0.226:8000',
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
      '/webrtc': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
      '/api': {
        // target: 'http://192.168.0.226:8000',
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})