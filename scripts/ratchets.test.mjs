import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { compare, measure } from './ratchets.mjs'

function measured(files) {
  const root = mkdtempSync(join(tmpdir(), 'ratchets-'))
  try {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(root, path)), { recursive: true })
      writeFileSync(join(root, path), content)
    }
    return measure(root)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

const panel = 'apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx'
const node = 'apps/desktop/src/renderer/domains/workflows/components/Node.tsx'
const base = {
  [panel]: "handleChange('selector', v); handleChange('retryCount', v)",
  'apps/desktop/src/renderer/domains/workflows/components/config-panels/Loop.test.tsx': "onChange('onlyInTests', v)",
  'apps/backend/src/autoflow/executor.py': "config.get('selector')",
  [node]: "<div className='bg-blue-500' />",
  'apps/desktop/src/renderer/app/Icon.tsx': "import { X } from '@phosphor-icons/react'",
  'docs/qa/shot.png': 'png',
}

test('measures the four ratchet counters and ignores test files', () => {
  assert.deepEqual(measured(base), { unreadConfigKeys: ['retryCount'], paletteClasses: 1, secondIconLibraryFiles: 1, docsPng: 1 })
})

test('fails on each new unread key, palette class, icon import and PNG, naming the item', () => {
  const current = measured({
    ...base,
    [panel]: base[panel] + "; onChange('timeoutAction', v)",
    [node]: "<div className='bg-blue-500 text-red-700' />",
    'apps/desktop/src/renderer/app/Other.tsx': "import { Y } from '@phosphor-icons/react'",
    'docs/qa/another.PNG': 'png',
  })
  const { failures } = compare(current, measured(base))
  assert.equal(failures.length, 4)
  assert.match(failures[0], /timeoutAction/)
  assert.match(failures.join('\n'), /paletteClasses 从 1 增加到 2/)
  assert.match(failures.join('\n'), /secondIconLibraryFiles 从 1 增加到 2/)
  assert.match(failures.join('\n'), /docsPng 从 1 增加到 2/)
})

test('reports improvements without failing', () => {
  const current = measured({ ...base, [panel]: "handleChange('selector', v)" })
  assert.deepEqual(compare(current, measured(base)), { failures: [], improvements: ['unreadConfigKeys'] })
})

for (const [name, files, pattern] of [
  ['config', { [panel]: "onChange('timeoutAction', v)" }, /timeoutAction/],
  ['palette', { [node]: "<div className='bg-blue-500 text-red-700' />" }, /paletteClasses/],
  ['icons', { 'apps/desktop/src/renderer/app/Other.tsx': "import { Y } from '@phosphor-icons/react'" }, /secondIconLibraryFiles/],
  ['PNG', { 'docs/qa/another.PNG': 'png' }, /docsPng/],
]) {
  test(`rejects an isolated ${name} regression`, () => {
    const { failures } = compare(measured({ ...base, ...files }), measured(base))
    assert.equal(failures.length, 1)
    assert.match(failures[0], pattern)
  })
}

test('quote style does not bypass configuration or icon checks', () => {
  const current = measured({
    ...base,
    [panel]: 'handleChange("timeoutAction", v)',
    'apps/desktop/src/renderer/app/Other.tsx': 'import { Y } from "@phosphor-icons/react"',
  })
  assert.deepEqual(current.unreadConfigKeys, ['timeoutAction'])
  assert.equal(current.secondIconLibraryFiles, 2)
})
