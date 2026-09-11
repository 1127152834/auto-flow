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
