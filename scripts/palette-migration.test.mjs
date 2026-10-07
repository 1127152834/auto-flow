import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { test } from 'node:test'
import { migrateText } from './palette-migration.mjs'

const map = { text: { 'gray-500': 'text-muted' }, bg: { 'gray-50': 'bg-surface-subtle' }, border: {} }
const run = (src, ext = '.tsx') => migrateText(src, ext, map)

test('basic replacement', () => {
  const r = run('const a = "text-gray-500 flex"')
  assert.equal(r.text, 'const a = "text-muted flex"')
  assert.equal(r.replaced, 1)
})

test('keeps variant prefixes, important prefix and opacity suffix', () => {
  const r = run('const a = "hover:dark:md:text-gray-500 !bg-gray-50/50 hover:!text-gray-500"')
  assert.equal(r.text, 'const a = "hover:dark:md:text-muted !bg-surface-subtle/50 hover:!text-muted"')
  assert.equal(r.replaced, 3)
})

test('unmapped classes stay and are listed with line', () => {
  const r = run('x\nconst a = "text-blue-600 text-blue-600 text-gray-500"')
  assert.match(r.text, /text-blue-600 text-blue-600 text-muted/)
  assert.deepEqual(r.unmapped.map(u => [u.cls, u.line]), [['text-blue-600', 2], ['text-blue-600', 2]])
})

test('ignores comments and non-string text, handles css', () => {
  const src = '// text-gray-500\n/* bg-gray-50 */\n<p>text-gray-500</p>\nconst a = "bg-gray-50"'
  const r = run(src)
  assert.equal(r.text, '// text-gray-500\n/* bg-gray-50 */\n<p>text-gray-500</p>\nconst a = "bg-surface-subtle"')
  const c = run('/* text-gray-500 */\n.a { @apply text-gray-500; }', '.css')
  assert.equal(c.text, '/* text-gray-500 */\n.a { @apply text-muted; }')
})

test('does not touch longer identifiers', () => {
  assert.equal(run('"my-text-gray-500 text-gray-5000"').replaced, 0)
})

test('idempotent', () => {
  const once = run('"text-gray-500 text-blue-600"')
  const twice = run(once.text)
  assert.equal(twice.text, once.text)
  assert.equal(twice.replaced, 0)
})

test('cli: dry-run does not write, --write does, report outside docs', () => {
  const dir = mkdtempSync(join(tmpdir(), 'pm-'))
  const file = join(dir, 'a.tsx')
  const report = join(dir, 'out', 'report.md')
  const src = 'const a = "text-gray-500 text-blue-600"\n'
  writeFileSync(file, src)
  const cli = (...a) => spawnSync(process.execPath, [join(import.meta.dirname, 'palette-migration.mjs'), ...a], { encoding: 'utf8' })
  let p = cli(file, '--report', report)
  assert.equal(p.status, 0, p.stderr)
  assert.equal(readFileSync(file, 'utf8'), src)
  assert.match(p.stdout, /替换 1/)
  assert.match(readFileSync(report, 'utf8'), /text-blue-600/)
  p = cli(file, '--write', '--report', report)
  assert.equal(readFileSync(file, 'utf8'), 'const a = "text-muted text-blue-600"\n')
  p = cli(file, '--write', '--report', report)
  assert.match(p.stdout, /替换 0/)
  mkdirSync(join(dir, 'docs'))
  assert.notEqual(cli(file, '--report', join(dir, 'docs', 'r.md')).status, 0)
  assert.ok(!existsSync(join(dir, 'docs', 'r.md')))
})

test('apostrophes in JSX text and quotes in regex literals do not hide later classes', () => {
  const r = run(["const x = <p>Don't</p>", "const a = 'bg-gray-50 text-gray-500'", 'const b = "text-gray-500"'].join('\n'))
  assert.equal(r.replaced, 3)
  assert.match(r.text, /'bg-surface-subtle text-muted'/)
  assert.match(r.text, /"text-muted"/)
})

test('template literal static parts are migrated, expressions are left alone', () => {
  const r = run('const a = `text-gray-500 ${on ? "bg-gray-50" : "x"} text-gray-500`')
  assert.equal(r.text, 'const a = `text-muted ${on ? "bg-surface-subtle" : "x"} text-muted`')
  assert.equal(r.replaced, 3)
})

test('cli: a path without --report is still processed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'pm-'))
  const file = join(dir, 'a.tsx')
  writeFileSync(file, 'const a = "text-gray-500"\n')
  const cli = (...a) => spawnSync(process.execPath, [join(import.meta.dirname, 'palette-migration.mjs'), ...a], { encoding: 'utf8' })
  const p = cli(file)
  assert.equal(p.status, 0, p.stderr)
  assert.match(p.stdout, /替换 1/)
  assert.equal(readFileSync(file, 'utf8'), 'const a = "text-gray-500"\n')
  assert.equal(cli(file, '--write').status, 0)
  assert.equal(readFileSync(file, 'utf8'), 'const a = "text-muted"\n')
})
