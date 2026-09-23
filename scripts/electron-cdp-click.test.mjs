import assert from 'node:assert/strict'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import { clickElement } from './electron-cdp.mjs'

test('click waits for an uncovered stable target and dispatches once at its final position', async () => {
  let reads = 0
  const commands = []
  const target = { disabled: false, textContent: 'Select', getClientRects: () => [1], scrollIntoView() {}, getAttribute: () => null, contains: item => item === target,
    getBoundingClientRect: () => ({ x: reads < 3 ? 100 : 300, y: 20, width: 100, height: 40 }) }
  const cdp = {
    evaluate: async expression => { reads++; return runInNewContext(expression, { document: { querySelectorAll: () => [target], elementFromPoint: () => reads === 1 ? {} : target } }) },
    command: async (method, params) => { commands.push({ method, params }); if (method === 'Input.dispatchMouseEvent') assert.ok(reads >= 4) },
  }
  await clickElement(cdp, 'Select', 'button')
  assert.deepEqual(commands.filter(item => item.method === 'Input.dispatchMouseEvent').map(item => ({ ...item.params })), [
    { type: 'mousePressed', x: 350, y: 40, button: 'left', clickCount: 1 },
    { type: 'mouseReleased', x: 350, y: 40, button: 'left', clickCount: 1 },
  ])
})
