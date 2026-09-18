import { expect, it } from 'vitest'
import { bindableRecords, selectedTargets } from './record-targets'

const record = {
  alias: '主账号',
  recordRef: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '主账号' } },
  linkRevision: 1,
  currentEnvironmentId: null,
}

it('keeps declared record targets and selected replace choices', () => {
  const items = bindableRecords([record, { alias: '查询' }, record])
  expect(items).toHaveLength(1)
  expect(items[0]?.alias).toBe('主账号')
  expect(selectedTargets(items, new Set([items[0]!.key]), true)).toEqual([{
    recordRef: record.recordRef,
    expectedLinkRevision: 1,
    replaceAllowed: true,
  }])
  expect(selectedTargets(items, new Set(), false)).toEqual([])
})
