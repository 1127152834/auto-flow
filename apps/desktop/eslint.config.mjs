import { readFileSync } from 'node:fs'
import tseslint from 'typescript-eslint'

// Frozen-source payload types are retained during parity migration. New adapters remain strict.
const sourceFiles = JSON.parse(readFileSync(new URL('./src/renderer/domains/workflows/source-manifest.json', import.meta.url), 'utf8'))
  .filter(entry => /\.tsx?$/.test(entry.target))
  .map(entry => entry.target.replace('apps/desktop/', ''))

export default tseslint.config(
  {
    ignores: ['dist/**', 'out/**', 'node_modules/**'],
  },
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{js,ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  { files: sourceFiles, rules: { '@typescript-eslint/no-explicit-any': 'off' } },
)
