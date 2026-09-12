import react from '@vitejs/plugin-react'
import { defineConfig, configDefaults } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    exclude: [...configDefaults.exclude, 'tests/ui/**'],
  },
})
