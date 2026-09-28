import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import test from 'node:test'

const require = createRequire(import.meta.url)

test('Monaco ships a sanitizer at or above the reviewed 3.4.15 security baseline', async () => {
  // Monaco embeds its own implementation: the root DOMPurify lock entry alone
  // cannot establish that the code actually bundled by the editor is patched.
  const monaco = dirname(require.resolve('monaco-editor/package.json'))
  const source = await readFile(join(monaco, 'esm/vs/base/browser/dompurify/dompurify.js'), 'utf8')
  const match = source.match(/DOMPurify\.version\s*=\s*['"](\d+)\.(\d+)\.(\d+)['"]/)
  assert.ok(match, 'embedded sanitizer version must remain independently inspectable')
  const version = match.slice(1).map(Number)
  const minimum = [3, 4, 15]
  const differing = version.findIndex((part, index) => part !== minimum[index])
  assert.ok(differing < 0 || version[differing] > minimum[differing], `embedded DOMPurify ${version.join('.')} is below 3.4.15`)
})
