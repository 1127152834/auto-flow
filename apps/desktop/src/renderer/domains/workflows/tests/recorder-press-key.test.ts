import { expect, it } from 'vitest'
import { excludedModuleTypes, moduleCategories } from '../lib/moduleCatalog'
import { buildRecordedNodes, type RecEvent } from '../lib/recordingGeneration'

it('maps recorded key presses to the runnable web press_key node (remediation M1 R1-16)', () => {
  const { nodes } = buildRecordedNodes([
    { type: 'keypress', key: 'Enter', selector: '#input' },
    { type: 'keypress', key: 'Tab' },
  ], false)
  expect(nodes.map(node => [node.data.moduleType, node.data.key, node.data.targetType, node.data.selector]))
    .toEqual([['press_key', 'Enter', 'element', '#input'], ['press_key', 'Tab', 'focused', undefined]])
})

it('every node the recorder can generate is in the runnable catalog', () => {
  const events: RecEvent[] = [
    { type: 'navigate', url: 'https://local.test/a', ts: 1 },
    { type: 'click', selector: '#go', ts: 2 },
    { type: 'dblclick', selector: '#go', ts: 3 },
    { type: 'input', selector: '#name', value: 'x', ts: 4 },
    { type: 'select', selector: '#s', value: 'one', ts: 5 },
    { type: 'check', selector: '#c', value: true, ts: 6 },
    { type: 'keypress', key: 'Enter', selector: '#name', ts: 7 },
    { type: 'drag', selector: '#from', targetSelector: '#to', ts: 8 },
    { type: 'upload', selector: '#file', fileName: 'a.txt', ts: 9 },
    { type: 'scroll', dy: 300, ts: 10 },
    { type: 'click', selector: '#in-frame', _frame: { selector: 'iframe#one' }, ts: 11 },
    { type: 'click', selector: '#main', _frame: { main: true }, ts: 12 },
  ]
  const catalog = new Set(moduleCategories.flatMap(category => category.modules))
  for (const autoWait of [true, false]) {
    for (const node of buildRecordedNodes(events, autoWait).nodes) {
      const type = node.data.moduleType
      expect(excludedModuleTypes.has(type), type).toBe(false)
      expect(catalog.has(type), type).toBe(true)
    }
  }
})
