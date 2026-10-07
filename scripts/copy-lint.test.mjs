import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'
import { lint } from './copy-lint.mjs'

const entries = [
  { term: '执行代次', preferred: '本次运行', reason: 'r', allowedIn: [] },
  { term: 'runId', preferred: '本次运行', reason: 'r', allowedIn: ['apps/desktop/src/allowed.ts'] },
]
const src = 'apps/desktop/src/'

function linted(files) {
  const root = mkdtempSync(join(tmpdir(), 'copy-lint-'))
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(root, path)), { recursive: true })
      writeFileSync(join(root, path), content)
    }
    return lint(root, entries)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

test('reports string literals, template text and JSX text with file, line, term and preferred wording', () => {
  const hits = linted({
    [`${src}a.tsx`]: "const a = '执行代次已变化'\nconst b = `第 ${n} 个执行代次`\nexport const C = () => <p>当前执行代次</p>\n",
  })
  assert.deepEqual(hits, [
    { file: `${src}a.tsx`, line: 1, term: '执行代次', preferred: '本次运行' },
    { file: `${src}a.tsx`, line: 2, term: '执行代次', preferred: '本次运行' },
    { file: `${src}a.tsx`, line: 3, term: '执行代次', preferred: '本次运行' },
  ])
})

test('ignores comments, identifiers, type names, bare keys and import paths', () => {
  const hits = linted({
    [`${src}b.ts`]: "// 执行代次\n/** runId */\nconst runId = 1\ntype T = { runId: string }\nconst k = ['runId']\nconst o = { 'runId': 1 }\nimport x from './runId'\nconst c = 'runId' in o\n",
  })
  assert.deepEqual(hits, [])
})

test('matches ASCII terms on word boundaries only', () => {
  assert.deepEqual(linted({ [`${src}c.ts`]: "const a = '请提供 runIdentity 或 runId 值'\nconst b = 'myrunIds'\n" }).map(h => h.line), [1])
})

test('skips tests, generated, api clients, mocks, development and documentation paths', () => {
  const body = "export const a = '执行代次'\n"
  assert.deepEqual(linted({
    [`${src}x.test.tsx`]: body, [`${src}generated.ts`]: body, [`${src}foo-api.ts`]: body, [`${src}mock-data.ts`]: body,
    [`${src}development/d.ts`]: body, [`${src}documentation/d.ts`]: body,
  }), [])
})

test('allowedIn exempts only the listed term in the listed path', () => {
  const body = "export const a = '必须指定 runId，且执行代次有效'\n"
  const hits = linted({ [`${src}allowed.ts`]: body, [`${src}other.ts`]: body })
  assert.deepEqual(hits.map(h => `${h.file}:${h.term}`), [`${src}allowed.ts:执行代次`, `${src}other.ts:执行代次`, `${src}other.ts:runId`])
})

test('CLI exits 1 on hits, 0 with --report-only, 0 when clean', () => {
  const script = join(dirname(fileURLToPath(import.meta.url)), 'copy-lint.mjs')
  const root = mkdtempSync(join(tmpdir(), 'copy-lint-cli-'))
  try {
    mkdirSync(join(root, 'apps/desktop/src/shared/copy'), { recursive: true })
    writeFileSync(join(root, 'apps/desktop/src/shared/copy/glossary.json'), JSON.stringify(entries))
    writeFileSync(join(root, 'apps/desktop/src/a.ts'), "export const a = '执行代次'\n")
    const run = args => spawnSync(process.execPath, [script, '--root', root, ...args], { encoding: 'utf8' })
    const failed = run([])
    assert.equal(failed.status, 1)
    assert.match(failed.stdout, /apps\/desktop\/src\/a\.ts:1:执行代次:本次运行/)
    assert.equal(run(['--report-only']).status, 0)
    writeFileSync(join(root, 'apps/desktop/src/a.ts'), "export const a = 1\n")
    assert.equal(run([]).status, 0)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
