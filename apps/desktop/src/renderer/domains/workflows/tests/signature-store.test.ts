import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'
import { validateSignature, type SignatureInputDraft } from '../lib/signatureDocument'

const RAW = {
  inputs: [{ key: 'account', name: '账号', extraInput: 1, fields: [
    { key: 'user', name: '用户名', type: 'string', required: true, sensitive: false, sample: 'alice', hint: 'keep' },
    { key: 'password', name: '密码', type: 'string', required: true, sensitive: true },
  ] }],
  outputs: [{ key: 'ok' }],
}
const sig = () => useSignatureStore.getState()
const workflow = (extra: object = {}) => ({ id: 'w1', name: '流程', nodes: [], edges: [], variables: [], ...extra })

beforeEach(() => {
  useWorkflowStore.getState().clearWorkflow()
  sig().reset()
})

describe('signature store', () => {
  it('loads a stored signature clean and editable', () => {
    sig().load(structuredClone(RAW))
    expect(sig().inputs[0].fields.map(f => f.key)).toEqual(['user', 'password'])
    expect(sig().dirty).toBe(false)
    expect(sig().readOnly).toBe(false)
  })

  it('an invalid draft stays unsaved after a document save instead of looking saved', () => {
    sig().load(structuredClone(RAW))
    sig().addInput({ key: 'order', name: '订单' })
    sig().addField('order', { key: 'no', name: '单号', type: 'string' })
    sig().addField('order', { key: 'no', name: '重复', type: 'string' })
    expect(sig().canSave).toBe(false)
    expect(sig().serialize()).toBeUndefined()
    sig().markSaved()
    expect(sig().dirty).toBe(true)
    sig().removeField('order', 'no')
    expect(sig().canSave).toBe(true)
    sig().markSaved()
    expect(sig().dirty).toBe(false)
  })

  it('adds, edits and removes inputs and fields, tracking dirty', () => {
    sig().load(structuredClone(RAW))
    sig().addInput({ key: 'order', name: '订单' })
    sig().addField('order', { key: 'no', name: '单号', type: 'string' })
    sig().updateField('order', 'no', { name: '订单号', required: true, sample: 'A1' })
    expect(sig().dirty).toBe(true)
    const order = sig().inputs.find(i => i.key === 'order')!
    expect(order.fields[0]).toMatchObject({ name: '订单号', required: true, sample: 'A1' })
    sig().removeField('order', 'no')
    sig().removeInput('order')
    expect(sig().inputs.map(i => i.key)).toEqual(['account'])
  })

  it('does not become dirty when an edit changes nothing', () => {
    sig().load(structuredClone(RAW))
    sig().updateField('account', 'user', { name: '用户名' })
    expect(sig().dirty).toBe(false)
  })

  it('drops the sample when a field becomes sensitive', () => {
    sig().load(structuredClone(RAW))
    sig().updateField('account', 'user', { sensitive: true })
    expect(sig().inputs[0].fields[0].sample).toBeUndefined()
    expect(sig().issues).toEqual([])
  })

  it('serializes edits back while keeping unknown keys', () => {
    sig().load(structuredClone(RAW))
    sig().updateField('account', 'user', { name: '登录名', sample: undefined })
    const out = sig().serialize() as { outputs: unknown; inputs: { extraInput: unknown; fields: unknown[] }[] }
    expect(out.outputs).toEqual([{ key: 'ok' }])
    expect(out.inputs[0].extraInput).toBe(1)
    expect(out.inputs[0].fields[0]).toEqual({ key: 'user', name: '登录名', type: 'string', required: true, sensitive: false, hint: 'keep' })
    expect(out.inputs[0].fields[1]).toEqual({ key: 'password', name: '密码', type: 'string', required: true, sensitive: true })
  })

  it('serializes nothing until the signature is edited', () => {
    sig().load(structuredClone(RAW))
    expect(sig().serialize()).toBeUndefined()
  })

  it('reports duplicate keys, bad types, bad samples and sensitive samples', () => {
    const inputs: SignatureInputDraft[] = [
      { key: 'a', name: 'A', rest: {}, fields: [
        { key: 'x', name: 'X', type: 'number', required: false, sensitive: false, sample: 'abc', rest: {} },
        { key: 'x', name: 'X2', type: 'string', required: false, sensitive: false, rest: {} },
        { key: 'p', name: 'P', type: 'string', required: false, sensitive: true, sample: 'pw', rest: {} },
        { key: 'd', name: 'D', type: 'date', required: false, sensitive: false, sample: '明天', rest: {} },
      ] },
      { key: 'a', name: 'dup', fields: [], rest: {} },
      { key: '1bad', name: 'bad', fields: [], rest: {} },
    ]
    const messages = validateSignature(inputs).map(i => i.message)
    expect(messages.some(m => m.includes('字段标识「x」重复'))).toBe(true)
    expect(messages.some(m => m.includes('流程输入标识「a」重复'))).toBe(true)
    expect(messages.filter(m => m.includes('样例')).length).toBe(3)
    expect(messages.some(m => m.includes('标识只能包含'))).toBe(true)
  })

  it('refuses to save an invalid signature', () => {
    sig().load(structuredClone(RAW))
    sig().addField('account', { key: 'user', name: '重复', type: 'string' })
    expect(sig().issues.length).toBeGreaterThan(0)
    expect(sig().serialize()).toBeUndefined()
    expect(sig().canSave).toBe(false)
  })

  it('becomes read-only and ignores edits when the stored signature has problems', () => {
    sig().load({ inputs: [{ key: '1x', fields: [] }] })
    expect(sig().readOnly).toBe(true)
    sig().addInput({ key: 'ok', name: 'ok' })
    expect(sig().inputs.map(i => i.key)).toEqual(['1x'])
    expect(sig().dirty).toBe(false)
    expect(sig().serialize()).toBeUndefined()
  })

  it('becomes read-only when the server reports signature issues', async () => {
    sig().load(structuredClone(RAW))
    const get = vi.fn().mockResolvedValue({ success: true, data: { signature: null, signatureIssues: [{ path: 'signature.inputs.0', message: '流程输入格式不正确' }] } })
    await sig().refreshIssues('w1', get)
    expect(sig().readOnly).toBe(true)
    expect(sig().serverIssues).toEqual([{ path: 'signature.inputs.0', message: '流程输入格式不正确' }])
    sig().addInput({ key: 'n', name: 'n' })
    expect(sig().dirty).toBe(false)
  })
})

describe('editor store wiring', () => {
  it('leaves the document bytes unchanged when the signature is not edited', () => {
    const strip = (text: string) => text.replace(/"(createdAt|updatedAt)": "[^"]*"/g, '')
    const before = strip(useWorkflowStore.getState().exportWorkflow())
    sig().load(structuredClone(RAW))
    expect(strip(useWorkflowStore.getState().exportWorkflow())).toBe(before)
  })

  it('imports the signature from the opened workflow and saves the edited one', () => {
    useWorkflowStore.getState().importWorkflow(workflow({ signature: structuredClone(RAW) }))
    expect(sig().inputs[0].key).toBe('account')
    expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false)
    sig().updateField('account', 'user', { name: '登录名' })
    expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
    const doc = JSON.parse(useWorkflowStore.getState().exportWorkflow())
    expect(doc.signature.inputs[0].fields[0].name).toBe('登录名')
    expect(doc.signature.outputs).toEqual([{ key: 'ok' }])
    useWorkflowStore.getState().markAsSaved()
    expect(sig().dirty).toBe(false)
    expect(JSON.parse(useWorkflowStore.getState().exportWorkflow())).not.toHaveProperty('signature')
  })

  it('never writes a signature from a read-only workflow, and resets on clear', () => {
    useWorkflowStore.getState().importWorkflow(workflow({ signature: { inputs: [{ key: '1x' }] } }))
    expect(sig().readOnly).toBe(true)
    expect(JSON.parse(useWorkflowStore.getState().exportWorkflow())).not.toHaveProperty('signature')
    useWorkflowStore.getState().clearWorkflow()
    expect(sig().readOnly).toBe(false)
    expect(sig().inputs).toEqual([])
  })
})
