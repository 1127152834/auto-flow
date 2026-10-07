import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))

const MESSAGE = '输入与输出里还有没填好的地方，请先修正'
const signature = { inputs: [{ key: 'account', name: '账号', fields: [{ key: 'phone', name: '手机号', type: 'string', required: true, sensitive: false }] }] }
let writes: { method: string; path: string; body: Record<string, unknown> }[]

beforeEach(() => {
  writes = []
  useWorkflowStore.getState().clearWorkflow()
  useSignatureStore.getState().load(signature)
  setStudioTransport(async (input, init) => {
    const url = new URL(String(input))
    if (init?.method === 'POST' || init?.method === 'PUT') {
      const body = JSON.parse(String(init.body))
      if (url.pathname.startsWith('/api/workflows')) { writes.push({ method: init.method, path: url.pathname, body }); return Response.json({ ...body, id: body.id ?? 'wf-1', revision: 2 }) }
    }
    return mockRequest(input, init)
  })
})
afterEach(() => { cleanup(); setStudioTransport(mockRequest); history.replaceState(null, '', '/') })

const invalidate = () => useSignatureStore.getState().updateFieldAt(0, 0, { key: '1bad' })

describe('签名保存守卫', () => {
  it('refuses to save an invalid signature draft and keeps it unsaved', async () => {
    invalidate()
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes(MESSAGE))).toBe(true))
    expect(writes).toEqual([])
    expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
    expect(useSignatureStore.getState().dirty).toBe(true)
  })

  it('saves an edited valid signature with the document and marks it saved', async () => {
    useSignatureStore.getState().updateFieldAt(0, 0, { name: '电话' })
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(writes).toHaveLength(1))
    expect(writes[0].body.signature).toMatchObject({ inputs: [{ key: 'account', fields: [{ key: 'phone', name: '电话' }] }] })
    await waitFor(() => expect(useSignatureStore.getState().dirty).toBe(false))
  })

  it.each([['playwright'], ['selenium']])('updates the stored workflow with the edited signature before exporting (%s)', async format => {
    useWorkflowStore.setState({ id: 'wf-1', nodes: [{ id: 'n1', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击' } }] as never })
    history.replaceState(null, '', '/?workflowId=wf-1')
    useSignatureStore.getState().updateFieldAt(0, 0, { name: '电话' })
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: '导出' }))
    if (format === 'selenium') fireEvent.click(await screen.findByText('Selenium Python'))
    fireEvent.click(await screen.findByRole('button', { name: '立即导出' }))
    await waitFor(() => expect(writes.some(write => write.method === 'PUT')).toBe(true))
    expect(writes.find(write => write.method === 'PUT')!.body.signature).toMatchObject({ inputs: [{ fields: [{ name: '电话' }] }] })
  })

  it.each([['update', 'wf-1'], ['create', '']])('marks the signature saved after the export-save succeeds (%s)', async (_kind, id) => {
    useWorkflowStore.setState({ id, nodes: [{ id: 'n1', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击' } }] as never })
    if (id) history.replaceState(null, '', '/?workflowId=wf-1')
    useSignatureStore.getState().updateFieldAt(0, 0, { name: '电话' })
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: '导出' }))
    fireEvent.click(await screen.findByRole('button', { name: '立即导出' }))
    await waitFor(() => expect(writes.length).toBeGreaterThan(0))
    await waitFor(() => expect(useSignatureStore.getState().dirty).toBe(false))
  })

  it('does not export-save when the signature draft is invalid', async () => {
    useWorkflowStore.setState({ id: 'wf-1', nodes: [{ id: 'n1', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击' } }] as never })
    history.replaceState(null, '', '/?workflowId=wf-1')
    invalidate()
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: '导出' }))
    fireEvent.click(await screen.findByRole('button', { name: '立即导出' }))
    await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes(MESSAGE))).toBe(true))
    expect(writes).toEqual([])
  })
})

describe('输入与输出入口', () => {
  it('opens the panel from the more menu', async () => {
    render(<Toolbar />)
    fireEvent.pointerDown(screen.getByRole('button', { name: '更多操作' }), { button: 0, ctrlKey: false })
    fireEvent.click(await screen.findByRole('menuitem', { name: '输入与输出' }))
    expect(await screen.findByRole('dialog', { name: '输入与输出' })).toBeTruthy()
  })
})
