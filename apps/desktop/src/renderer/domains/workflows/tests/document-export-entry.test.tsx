import { webcrypto } from 'node:crypto'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore } from '../editor-store'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
import { decryptWorkflow } from '../lib/workflowCrypto'

let blobs: Blob[]
let downloads: string[]
let requests: { path: string; method: string; body: Record<string, unknown> | undefined }[]
let failUpdate: boolean
let failExport: boolean
const blobText = (blob: Blob) => new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsText(blob) })
beforeEach(() => {
  blobs = []; downloads = []; requests = []; failUpdate = false; failExport = false
  vi.stubGlobal('crypto', webcrypto)
  vi.spyOn(URL, 'createObjectURL').mockImplementation(blob => { blobs.push(blob as Blob); return 'blob:export-fixture' })
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { downloads.push(this.download) })
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.setState({ name: '导出入口验收' })
  useWorkflowStore.getState().addNode('input_text', { x: 10, y: 20 })
  const node = useWorkflowStore.getState().nodes[0]
  useWorkflowStore.getState().updateNodeData(node.id, { selector: '#name', text: '原文 ${name}' })
  useWorkflowStore.getState().addVariable({ name: 'name', value: '中文', type: 'string', scope: 'global' })
  setStudioTransport(async (input, init) => {
    const path = new URL(String(input)).pathname
    requests.push({ path, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined })
    if (path === '/api/workflows' && init?.method === 'POST') return Response.json({ id: 'export-fixture' })
    if (path === '/api/workflows/export-fixture' && init?.method === 'PUT') return failUpdate ? Response.json({ error: '更新失败，保留草稿' }, { status: 503 }) : Response.json({ id: 'export-fixture' })
    if (path.includes('/export-script') || path.includes('/export-playwright')) return failExport ? Response.json({ error: '脚本服务失败' }, { status: 503 }) : Response.json({ code: '# MOCK SERVICE FIXTURE — not executable automation', filename: 'fixture-script.txt' })
    if (path === '/api/workflow-bundle/export') return failExport ? Response.json({ error: '依赖文件缺失' }, { status: 404 }) : Response.json({ success: true, bundle: { __fixture: true, ...JSON.parse(String(init?.body)) } })
    return mockRequest(input, init)
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setStudioTransport(mockRequest) })
function openExport(label: string, mount = true) {
  if (mount) render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: /^导出$/ }))
  fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }))
  fireEvent.click(screen.getByRole('button', { name: '立即导出' }))
}
it.each(['JSON 格式', 'Markdown 文档', '加密分享包', '整包（含依赖）', 'Playwright Python', 'Selenium Python', 'Playwright JavaScript'])('exports through the actual %s selection and preserves the draft', async label => {
  const before = structuredClone({ id: useWorkflowStore.getState().id, name: useWorkflowStore.getState().name, nodes: useWorkflowStore.getState().nodes, edges: useWorkflowStore.getState().edges, variables: useWorkflowStore.getState().variables })
  openExport(label.replace(/[（）]/g, '.'))
  if (label === '加密分享包') {
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'test-password' } })
    fireEvent.click(screen.getByRole('button', { name: '加密导出' }))
  }
  await waitFor(() => expect(downloads).toHaveLength(1))
  const text = await blobText(blobs[0])
  if (label === 'JSON 格式') expect(JSON.parse(text)).toMatchObject({ name: '导出入口验收', nodes: [{ data: { selector: '#name', text: '原文 ${name}' } }], variables: expect.arrayContaining([{ name: 'name', value: '中文', type: 'string', scope: 'global' }]) })
  else if (label === 'Markdown 文档') { expect(text).toContain('导出入口验收'); expect(text).toContain('#name'); expect(text).toContain('原文 ${name}') }
  else if (label === '加密分享包') { expect(text).not.toContain('原文 ${name}'); const plain = await decryptWorkflow(JSON.parse(text), 'test-password'); expect(JSON.parse(plain).nodes[0].data.text).toBe('原文 ${name}'); await expect(decryptWorkflow(JSON.parse(text), 'wrong')).rejects.toThrow() }
  else if (label === '整包（含依赖）') { expect(JSON.parse(text).content.nodes[0].data.selector).toBe('#name'); expect(requests.some(r => r.path === '/api/workflow-bundle/export')).toBe(true) }
  else { expect(text).toContain('MOCK SERVICE FIXTURE'); expect(requests.some(r => r.path === '/api/workflows' && r.method === 'POST')).toBe(true); expect(requests.some(r => /export-script|export-playwright/.test(r.path))).toBe(true) }
  expect(useWorkflowStore.getState()).toMatchObject(before)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it.each(['Playwright Python', 'Selenium Python', 'Playwright JavaScript'])('does not export stale service content after update failure: %s', async label => {
  openExport(label)
  await waitFor(() => expect(downloads).toHaveLength(1))
  await waitFor(() => expect(screen.queryByRole('button', { name: '立即导出' })).toBeNull())
  downloads = []; requests = []; failUpdate = true
  openExport(label, false)
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('更新失败'))).toBe(true))
  expect(requests.some(r => /export-script|export-playwright/.test(r.path))).toBe(false)
  expect(downloads).toEqual([])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it.each(['Playwright Python', 'Selenium Python', 'Playwright JavaScript', '整包.含依赖.'])('does not download after service rejection: %s', async label => {
  failExport = true
  openExport(label)
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.level === 'error')).toBe(true))
  expect(downloads).toEqual([])
  expect(useWorkflowStore.getState().nodes).toHaveLength(1)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('cancels the format dialog without requests or downloads', () => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: /^导出$/ }))
  fireEvent.click(screen.getByRole('button', { name: /^取消$/ }))
  expect(requests.some(r => /export|workflows\/export-fixture/.test(r.path))).toBe(false)
  expect(downloads).toEqual([])
})
it('cancels encrypted export without changing the document', () => {
  openExport('加密分享包')
  fireEvent.keyDown(screen.getByPlaceholderText('请输入密码'), { key: 'Escape' })
  expect(downloads).toEqual([])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
