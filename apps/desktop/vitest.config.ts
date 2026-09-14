import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/renderer/domains/workflows/tests/setup-connection.ts'],
    maxWorkers: 4,
  },
})
