import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'
import tailwind from 'tailwindcss'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()]
  },
  preload: {
    plugins: [externalizeDepsPlugin()]
  },
  renderer: {
    resolve: {
      alias: {
        '@': resolve('src/frontend'),
        '@components': resolve('src/frontend/components'),
        '@pages': resolve('src/frontend/components/pages'),
        '@hooks': resolve('src/frontend/hooks'),
        '@store': resolve('src/frontend/store'),
        '@utils': resolve('src/frontend/utils'),
        '@types': resolve('src/frontend/types'),
        '@services': resolve('src/frontend/services'),
        '@locales': resolve('src/frontend/locales')
      }
    },
    plugins: [react()]
  }
})
