import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'
import { importDroppedWorkflows } from '../lib/droppedWorkflows'
import * as crypto from '../lib/workflowCrypto'

const payload = JSON.stringify({ nodes: [{ id: 'imported', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'print_log', config: { message: '拖入内容' } } }], edges: [], variables: [] })
const envelope = JSON.stringify({ __webrpa_encrypted: 'webrpa-encrypted-workflow', data: 'test-only', name: '测试包' })
const file = (text: () => Promise<string>, name = 'test.json') => ({ name, text } as File)
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
const dialogs = { promptPassword: vi.fn<() => Promise<string | null>>(), alert: vi.fn(async () => true) }
beforeEach(() => { store.getState().clearWorkflow(); vi.clearAllMocks() })
afterEach(() => vi.restoreAllMocks())

it('merges in file order, preserves same-document edits, and supports undo', async () => {
  const pending = deferred<string>()
  const operation = importDroppedWorkflows([file(() => pending.promise), file(async () => payload)], { x: 100, y: 200 }, dialogs)
  store.getState().addVariable({ name: 'kept', type: 'string', value: '编辑中', scope: 'global' })
  pending.resolve(payload)
  await operation
  expect(store.getState().nodes).toHaveLength(2)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(store.getState().nodes.map(n => n.position)).toEqual([{ x: 100, y: 200 }, { x: 100, y: 350 }])
  expect(store.getState().variables[0].name).toBe('kept')
  store.getState().undo()
  expect(store.getState().nodes).toHaveLength(1)
  expect(store.getState().variables[0].name).toBe('kept')
})
it.each(['reading', 'password', 'decrypting'])('does not import into a new document after %s', async stage => {
  const pending = deferred<string>()
  dialogs.promptPassword.mockImplementation(async () => stage === 'password' ? pending.promise : 'dummy')
  const decrypt = vi.spyOn(crypto, 'decryptWorkflow').mockImplementation(async () => stage === 'decrypting' ? pending.promise : payload)
  const operation = importDroppedWorkflows([file(() => stage === 'reading' ? pending.promise : Promise.resolve(envelope))], { x: 0, y: 0 }, dialogs)
  if (stage === 'password') await vi.waitFor(() => expect(dialogs.promptPassword).toHaveBeenCalledOnce())
  if (stage === 'decrypting') await vi.waitFor(() => expect(decrypt).toHaveBeenCalledOnce())
  store.getState().clearWorkflow()
  pending.resolve(stage === 'password' ? 'dummy' : payload)
  await operation
  expect(store.getState().nodes).toEqual([])
  expect(store.getState().hasUnsavedChanges).toBe(false)
  expect(store.getState().logs.at(-1)?.message).toContain('流程已切换')
})
it('invalidates an import even if the original document is reopened before reading ends', async () => {
  const originalId = store.getState().id
  const pending = deferred<string>()
  const operation = importDroppedWorkflows([file(() => pending.promise)], { x: 0, y: 0 }, dialogs)
  store.getState().clearWorkflow()
  store.setState({ id: originalId })
  pending.resolve(payload)
  await operation
  expect(store.getState().nodes).toEqual([])
})
it('serializes encrypted prompts and skips a cancelled file without discarding the next file', async () => {
  const pending = deferred<string | null>()
  dialogs.promptPassword.mockReturnValueOnce(pending.promise).mockResolvedValueOnce('dummy')
  vi.spyOn(crypto, 'decryptWorkflow').mockResolvedValue(payload)
  const operation = importDroppedWorkflows([file(async () => envelope, 'one.json'), file(async () => envelope, 'two.json')], { x: 0, y: 0 }, dialogs)
  await vi.waitFor(() => expect(dialogs.promptPassword).toHaveBeenCalledOnce())
  pending.resolve(null)
  await operation
  expect(dialogs.promptPassword).toHaveBeenCalledTimes(2)
  expect(store.getState().nodes).toHaveLength(1)
  expect(store.getState().logs.map(l => l.message)).toContain('已取消导入加密包: one.json')
})
it.each(['read', 'json', 'decrypt'])('reports %s errors without changing the document', async failure => {
  dialogs.promptPassword.mockResolvedValue('dummy')
  vi.spyOn(crypto, 'decryptWorkflow').mockRejectedValue(new Error('bad password'))
  await importDroppedWorkflows([file(async () => { if (failure === 'read') throw new Error('read failed'); return failure === 'json' ? 'damaged JSON' : envelope })], { x: 0, y: 0 }, dialogs)
  expect(store.getState().nodes).toEqual([])
  expect(store.getState().hasUnsavedChanges).toBe(false)
  expect(store.getState().logs.some(l => l.level === 'error')).toBe(true)
})
