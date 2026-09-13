import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'
export default defineConfig({ root: resolve(__dirname, 'src/renderer'), plugins: [react(), tailwindcss()], server: { host:'127.0.0.1', port:5175, strictPort:true } })
