import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  main: { plugins: [externalizeDepsPlugin()] },
  preload: { plugins: [externalizeDepsPlugin()] },
  renderer: { plugins: [react(), tailwindcss()], build: { rollupOptions: { input: { main: resolve(__dirname, 'src/renderer/index.html'), studio: resolve(__dirname, 'src/renderer/studio.html') } } } },
})
