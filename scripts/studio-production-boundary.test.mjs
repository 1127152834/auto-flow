import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../apps/desktop/src/renderer/studio.tsx', import.meta.url), 'utf8')

test('production Studio entry keeps preview mocks behind the Vite development boundary', () => {
  assert.doesNotMatch(source, /^import .*mock-server/m)
  assert.doesNotMatch(source, /^import .*StudioMockTools/m)
  assert.match(source, /import\.meta\.env\.DEV/)
})
