import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

for (const path of [
  'apps/desktop/package.json',
  'apps/backend/pyproject.toml',
]) {
  test(`required path exists: ${path}`, () => assert.equal(existsSync(path), true))
}

test('root scripts expose the foundation checks', () => {
  const packageJson = JSON.parse(readFileSync('package.json', 'utf8'))
  assert.equal(typeof packageJson.scripts['test:structure'], 'string')
  assert.equal(typeof packageJson.scripts['typecheck'], 'string')
})

// Regression guard: `TableHead` is the <thead> wrapper, so a header row must use the
// `TableHead` cell component (<th>). A `TableCell` (<td>) inside <thead> is hoisted out by
// the HTML parser and renders as an unstyled run of text above the table (PM6, 3x).
test('renderer table headers never nest a <td> inside <thead>', async () => {
  const { readdir, readFile } = await import('node:fs/promises')
  const { join } = await import('node:path')
  const offenders = []
  const roots = ['apps/desktop/src/renderer']
  while (roots.length > 0) {
    const dir = roots.pop()
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) { roots.push(path); continue }
      if (!entry.name.endsWith('.tsx') || entry.name.includes('.test.')) continue
      const source = await readFile(path, 'utf8')
      for (const match of source.matchAll(/<TableHead>([\s\S]*?)<\/TableHead>/g)) {
        if (match[1].includes('<TableCell')) offenders.push(path)
      }
    }
  }
  assert.deepEqual(offenders, [])
})
