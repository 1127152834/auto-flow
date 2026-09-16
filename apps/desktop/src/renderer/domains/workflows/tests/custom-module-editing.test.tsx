import { CreateCustomModuleDialog } from '../components/CreateCustomModuleDialog'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  for (const name of ['localStorage', 'sessionStorage']) {
    const data = new Map<string, string>()
    vi.stubGlobal(name, { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key), clear: () => data.clear() })
  }
})
import { Toolbar } from '../components/Toolbar'
import { customModulesApi } from '../api'
import { useWorkflowStore as store } from '../editor-store'
import { enterCustomModuleEditing, restoreMainWorkflow, saveCustomModuleEditing } from '../lib/customModuleEditing'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

let moduleId: string
beforeEach(async () => {
  sessionStorage.clear()
  setStudioTransport(mockRequest)
  store.getState().clearWorkflow()
  store.getState().setWorkflowNameWithHistory('主流程')
  store.getState().addVariable({ name: 'main', value: '原始草稿', type: 'string', scope: 'global' })
  const response = await customModulesApi.create({ name: 'reusable', display_name: '复用模块', description: '保留元数据', parameters: [], workflow: { nodes: [], edges: [], variables: [{ name: 'module_value', value: 1, type: 'number', scope: 'global' }] } })
  moduleId = response.data.id
})
afterEach(() => { cleanup(); sessionStorage.clear(); setStudioTransport(mockRequest); vi.restoreAllMocks() })

it('restores the main document identity, variables, dirty state and earlier history', async () => {
  const original = store.getState()
  expect(await enterCustomModuleEditing(moduleId)).toBe(true)
  expect(store.getState().variables[0].name).toBe('module_value')
  expect(store.getState().id).not.toBe(original.id)
  store.getState().updateVariable('module_value', 9)
  expect(restoreMainWorkflow()).toBe(true)
  expect(store.getState()).toMatchObject({ id: original.id, name: original.name, variables: original.variables, hasUnsavedChanges: true, history: original.history, historyIndex: original.historyIndex })
  store.getState().undo()
  expect(store.getState().variables).toEqual([])
  expect(sessionStorage.getItem('editingCustomModuleId')).toBeNull()
})
it('saves an empty module including variables and preserves its metadata', async () => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 8)
  expect(await saveCustomModuleEditing()).toBe(true)
  const loaded = await customModulesApi.get(moduleId)
  expect(loaded.data).toMatchObject({ name: 'reusable', description: '保留元数据', workflow: { nodes: [], variables: [{ name: 'module_value', value: 8 }] } })
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
it.each(['missing', 'changed'])('does not replace the draft when reading is %s', async mode => {
  const id = store.getState().id
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith(`/custom-modules/${moduleId}`)) {
      if (mode === 'missing') return Response.json({ error: 'offline' }, { status: 503 })
      store.getState().updateVariable('main', '读取时编辑')
    }
    return mockRequest(input, init)
  })
  expect(await enterCustomModuleEditing(moduleId)).toBe(false)
  expect(store.getState().id).toBe(id)
  expect(sessionStorage.getItem('editingCustomModuleId')).toBeNull()
})
it('does not enter when the main backup cannot be written', async () => {
  const id = store.getState().id
  vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('quota exceeded') })
  expect(await enterCustomModuleEditing(moduleId)).toBe(false)
  expect(store.getState().id).toBe(id)
})
it('does not clear the module or its session after a damaged backup', async () => {
  await enterCustomModuleEditing(moduleId)
  const id = store.getState().id
  sessionStorage.setItem('preEditWorkflowBackup', '{bad')
  expect(restoreMainWorkflow()).toBe(false)
  expect(store.getState().id).toBe(id)
  expect(sessionStorage.getItem('editingCustomModuleId')).toBe(moduleId)
})
it.each(['changed', 'failure'])('keeps module edits on %s save response', async mode => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 2)
  let release!: (response: Response) => void
  setStudioTransport(async (input, init) => init?.method === 'PUT' ? new Promise(resolve => { release = resolve }) : mockRequest(input, init))
  const pending = saveCustomModuleEditing()
  await waitFor(() => expect(release).toBeTypeOf('function'))
  if (mode === 'changed') store.getState().updateVariable('module_value', 3)
  release(Response.json(mode === 'failure' ? { success: false, error: 'disk full' } : { id: moduleId }))
  expect(await pending).toBe(false)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(sessionStorage.getItem('editingCustomModuleId')).toBe(moduleId)
})
it('keeps the editing draft when the saved revision conflicts', async () => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 21)
  let sent: Record<string, unknown> | undefined
  setStudioTransport(async (_input, init) => {
    sent = JSON.parse(String(init?.body))
    return Response.json({ error: { code: 'CUSTOM_MODULE_REVISION_CONFLICT', message: '模块已被其他窗口修改' } }, { status: 409 })
  })

  expect(await saveCustomModuleEditing()).toBe(false)
  expect(sent?.expectedRevision).toBe(1)
  expect(store.getState().variables[0].value).toBe(21)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(sessionStorage.getItem('editingCustomModuleId')).toBe(moduleId)
})
it.each(['保存后继续', '放弃修改', '取消'])('module exit handles %s through the real toolbar dialog', async choice => {
  const mainId = store.getState().id
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 7)
  render(<Toolbar />)
  fireEvent.click(await screen.findByRole('button', { name: '退出' }))
  fireEvent.click(await screen.findByRole('button', { name: choice }))
  if (choice === '取消') {
    expect(sessionStorage.getItem('editingCustomModuleId')).toBe(moduleId)
    expect(store.getState().variables[0].value).toBe(7)
  } else {
    await waitFor(() => expect(store.getState().id).toBe(mainId))
    expect(store.getState().variables[0].value).toBe('原始草稿')
    const loaded = await customModulesApi.get(moduleId)
    expect(loaded.data.workflow.variables[0].value).toBe(choice === '保存后继续' ? 7 : 1)
  }
})
it('failed save on exit keeps both module draft and main backup', async () => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 5)
  setStudioTransport(async (input, init) => init?.method === 'PUT' ? Response.json({ error: 'disk full' }, { status: 507 }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(await screen.findByRole('button', { name: '退出' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(store.getState().logs.some(log => log.message.includes('disk full'))).toBe(true))
  expect(sessionStorage.getItem('editingCustomModuleId')).toBe(moduleId)
  expect(sessionStorage.getItem('preEditWorkflowBackup')).toBeTruthy()
  expect(store.getState().variables[0].value).toBe(5)
})
it('Ctrl+S in module mode saves the module rather than a local workflow file', async () => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 4)
  const requests: string[] = []
  setStudioTransport(async (input, init) => { requests.push(String(input)); return mockRequest(input, init) })
  render(<Toolbar />)
  await act(async () => fireEvent.keyDown(window, { key: 's', ctrlKey: true }))
  await waitFor(() => expect(store.getState().hasUnsavedChanges).toBe(false))
  expect(requests.some(url => url.includes('save-to-folder'))).toBe(false)
  expect((await customModulesApi.get(moduleId)).data.workflow.variables[0].value).toBe(4)
})

it('new cannot discard the hidden main draft while module editing', async () => {
  await enterCustomModuleEditing(moduleId)
  const moduleDocumentId = store.getState().id
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  await waitFor(() => expect(store.getState().logs.some(log => log.message.includes('请先退出模块编辑'))).toBe(true))
  expect(store.getState().id).toBe(moduleDocumentId)
  expect(sessionStorage.getItem('preEditWorkflowBackup')).toBeTruthy()
})
it('switching modules resolves the module draft but retains the original main backup', async () => {
  const mainId = store.getState().id
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 6)
  render(<Toolbar />)
  const target = await customModulesApi.create({ name: 'second', workflow: { nodes: [], edges: [], variables: [] } })
  let pending!: Promise<boolean>
  await act(async () => { pending = enterCustomModuleEditing(target.data.id) })
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  expect(await pending).toBe(true)
  expect((await customModulesApi.get(moduleId)).data.workflow.variables[0].value).toBe(6)
  expect(JSON.parse(sessionStorage.getItem('preEditWorkflowBackup')!).id).toBe(mainId)
  expect(restoreMainWorkflow()).toBe(true)
  expect(store.getState().id).toBe(mainId)
})

it('creating from the canvas retains variables and structural node fields', async () => {
  store.getState().addNode('print_log', { x: 10, y: 20 })
  const node = store.getState().nodes[0]
  store.setState({ nodes: [{ ...node, style: { width: 280 }, extent: 'parent' }] })
  const before = JSON.parse(store.getState().exportWorkflow())
  let sent: Record<string, unknown> | undefined
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/custom-modules') && init?.method === 'POST') sent = JSON.parse(String(init.body))
    return mockRequest(input, init)
  })
  const close = vi.fn()
  render(<CreateCustomModuleDialog open onClose={close} />)
  fireEvent.change(screen.getByLabelText('模块名称（英文标识符）*'), { target: { value: 'created_from_canvas' } })
  fireEvent.change(screen.getByLabelText('显示名称*'), { target: { value: '创建验收' } })
  fireEvent.click(screen.getByRole('button', { name: '创建模块' }))
  await waitFor(() => expect(close).toHaveBeenCalledOnce())
  expect(sent?.workflow).toEqual({ nodes: before.nodes, edges: before.edges, variables: before.variables })
})

it('a fresh renderer cannot overwrite a module before its saved canvas is recovered', async () => {
  const mainId = store.getState().id
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 12)
  await saveCustomModuleEditing()
  store.getState().clearWorkflow() // A new renderer has no prior canvas but retains sessionStorage.
  expect(await saveCustomModuleEditing()).toBe(false)
  render(<Toolbar />)
  await waitFor(() => expect(store.getState().variables[0]?.value).toBe(12))
  expect(store.getState().hasUnsavedChanges).toBe(false)
  expect(JSON.parse(sessionStorage.getItem('preEditWorkflowBackup')!).id).toBe(mainId)
  fireEvent.click(screen.getByRole('button', { name: '退出' }))
  await waitFor(() => expect(store.getState().id).toBe(mainId))
})

it('reopening the currently edited module does not reload over its draft', async () => {
  await enterCustomModuleEditing(moduleId)
  store.getState().updateVariable('module_value', 19)
  const requests = vi.fn(mockRequest)
  setStudioTransport(requests)
  expect(await enterCustomModuleEditing(moduleId)).toBe(true)
  expect(requests).not.toHaveBeenCalled()
  expect(store.getState().variables[0].value).toBe(19)
  expect(store.getState().hasUnsavedChanges).toBe(true)
})
