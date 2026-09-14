import { expect, it } from 'vitest'
import { checkedExecutionLogPage, checkedWorkflowRunPage } from '../lib/executionLogContract'

const log = (sequence: number) => ({ id: `log-${sequence}`, sequence, timestamp: '2026-09-14T00:00:00Z', level: 'info' as const, message: 'ok' })

it('accepts an ordered log page owned by the requested run', async () => {
  const result = await checkedExecutionLogPage(Promise.resolve({ success: true, data: { runId: 'run', workflowId: 'workflow', items: [log(1), log(2)], total: 2, nextCursor: null } }), 'run')
  expect(result.success).toBe(true)
})

it.each([
  { runId: 'other', workflowId: 'workflow', items: [log(1)], total: 1, nextCursor: null },
  { runId: 'run', workflowId: 'workflow', items: [log(2), log(1)], total: 2, nextCursor: null },
  { runId: 'run', workflowId: 'workflow', items: [log(1)], total: 0, nextCursor: null },
])('rejects malformed or mismatched log pages', async data => {
  expect((await checkedExecutionLogPage(Promise.resolve({ success: true, data }), 'run')).success).toBe(false)
})

it('rejects run history without stable identities', async () => {
  const result = await checkedWorkflowRunPage(Promise.resolve({ success: true, data: { items: [{ runId: '', workflowId: 'workflow', documentId: 'document', startedAt: 'now', logCount: 0 }], total: 1, nextCursor: null } }))
  expect(result.success).toBe(false)
})
