import { expect, it } from 'vitest'
import { createBatchStartDraft, toBatchStartRequest, validateBatchStartDraft, type ParameterDefinition } from './start-schema'

const definitions: ParameterDefinition[] = [
  { parameterId: 'text', name: '文本', type: 'string', required: false, defaultValue: '' },
  { parameterId: 'count', name: '数量', type: 'number', required: false, defaultValue: 0 },
  { parameterId: 'enabled', name: '启用', type: 'boolean', required: false, defaultValue: false },
  { parameterId: 'empty', name: '空值', type: 'string', required: false, defaultValue: null },
  { parameterId: 'required', name: '必填', type: 'string', required: true },
]
it('keys defaults by stable parameter id and preserves empty scalar values', () => {
  expect(createBatchStartDraft(definitions, 10)).toEqual({ parameters: { text: '', count: 0, enabled: false, empty: null }, maxTasks: '10' })
})
it('distinguishes omitted required values and rejects invalid task counts', () => {
  expect(validateBatchStartDraft(createBatchStartDraft(definitions, 101), definitions)).toMatchObject({ maxTasks: expect.any(String), 'parameters.required': expect.any(String) })
})
it('builds the public batch contract without changing scalar types', () => {
  const draft = createBatchStartDraft(definitions, 10); draft.parameters.required = 'ok'
  expect(toBatchStartRequest(draft, definitions, 7)).toEqual({ expectedAutomationRevision: 7, parameters: { text: '', count: 0, enabled: false, empty: null, required: 'ok' }, maxTasks: 10, concurrency: 1 })
})
it('rejects stale parameter identities instead of leaking raw draft objects', () => {
  const draft = createBatchStartDraft(definitions); draft.parameters.required = 'ok'; draft.parameters.deleted = { raw: '12' }
  expect(validateBatchStartDraft(draft, definitions)).toHaveProperty('parameters.deleted')
  expect(toBatchStartRequest(draft, definitions, 7)).toBeNull()
})
it('serializes explicit unlimited only with required data and validates concurrency', () => {
  const draft = { ...createBatchStartDraft([]), unlimited: true, concurrency: '2' }
  expect(toBatchStartRequest(draft, [], 7, { allowUnlimited: true, dataBatch: true })).toMatchObject({ maxTasks: null, concurrency: 2 })
  expect(toBatchStartRequest(draft, [], 7)).toBeNull()
  expect(toBatchStartRequest({ ...draft, concurrency: '0' }, [], 7, { allowUnlimited: true, dataBatch: true })).toBeNull()
  expect(toBatchStartRequest({ ...draft, concurrency: '1.5' }, [], 7, { allowUnlimited: true, dataBatch: true })).toBeNull()
  expect(toBatchStartRequest({ ...draft, concurrency: '101' }, [], 7, { allowUnlimited: true, dataBatch: true })).toBeNull()
})

it('keeps parameter-only batch concurrency fixed at one', () => {
  const draft = { ...createBatchStartDraft([]), concurrency: '2' }
  expect(validateBatchStartDraft(draft, [])).toEqual({ concurrency: '参数型自动化的并发数固定为 1' })
  expect(toBatchStartRequest(draft, [], 7)).toBeNull()
  expect(toBatchStartRequest(draft, [], 7, { dataBatch: true })).toMatchObject({ concurrency: 2 })
})
