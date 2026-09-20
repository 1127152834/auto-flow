import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MCPConfigPanel } from '../components/MCPConfigPanel'
import { mcpApi } from '../api/mcp'
import { configureStudioConnection } from '../api/config'
const config = { mcpServers: { fixture: { command: 'node', disabled: false } } }
const configResponse = { ...config, revision: 0 }
const status = { servers: [], total_tools_injected: 0 }
const operations = [
  { name: 'config', call: () => mcpApi.config(), value: configResponse },
  { name: 'status', call: () => mcpApi.status(), value: status },
  { name: 'save', call: () => mcpApi.save(config), value: { success: true, saved: true, commandId: 'save', revision: 1 } },
  { name: 'reload', call: () => mcpApi.reload(), value: { connected: [], failed: [], disabled: [], total_servers: 0, commandId: 'reload', revision: 0 } },
]
let restore = () => {}
let restoreNext = () => {}
afterEach(() => { cleanup(); restoreNext(); restore(); restoreNext = () => {} })
for (const operation of operations) it(`${operation.name} rejects a receipt from the previous connection`, async () => {
  let resolve!: (response: Response) => void
  restore = configureStudioConnection('http://mcp.fixture', () => new Promise(done => { resolve = done }))
  const pending = operation.call()
  restoreNext = configureStudioConnection('http://next.fixture', async () => Response.json({}))
  resolve(Response.json(operation.value))
  const result = await pending
  expect(result.success).toBe(false)
  expect(result.data).toBeUndefined()
})
it('keeps a new server draft and blocks sending it after the connection changes', async () => {
  restore = configureStudioConnection('http://mcp.fixture', async input => Response.json(String(input).endsWith('/status') ? status : configResponse))
  render(<MCPConfigPanel />)
  await screen.findByText('fixture')
  fireEvent.click(screen.getByRole('button', { name: '添加' }))
  fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'), { target: { value: 'draft' } })
  fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'), { target: { value: 'node' } })
  const next = vi.fn(async () => Response.json({ success: true, saved: true, commandId: 'save', revision: 1 }))
  await act(async () => { restoreNext = configureStudioConnection('http://next.fixture', next) })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  expect(next).not.toHaveBeenCalled()
  expect(screen.getByPlaceholderText('例如 filesystem / weather / github')).toHaveProperty('value', 'draft')
  await screen.findByText(/连接已变更/)
})
it('ignores the previous configuration when its first read finishes after connection replacement', async () => {
  let resolve!: (response: Response) => void
  restore = configureStudioConnection('http://mcp.fixture', async input => String(input).endsWith('/status') ? Response.json(status) : new Promise(done => { resolve = done }))
  render(<MCPConfigPanel />)
  await act(async () => {
    restoreNext = configureStudioConnection('http://next.fixture', async () => Response.json({}))
    resolve(Response.json(configResponse))
  })
  expect(screen.queryByText('fixture')).toBeNull()
  expect((screen.getByRole('button', { name: '添加' }) as HTMLButtonElement).disabled).toBe(true)
  await screen.findByText(/连接已变更/)
})
it('a failed reload read disables writes against the stale configuration', async () => {
  let fail = false
  restore = configureStudioConnection('http://mcp.fixture', async input => {
    if (String(input).endsWith('/reload')) { fail = true; return Response.json({ connected: [], failed: [], disabled: [], total_servers: 0, commandId: 'reload', revision: 0 }) }
    if (String(input).endsWith('/status')) return Response.json(status)
    return fail ? Response.json({ error: '读取失败' }, { status: 503 }) : Response.json(configResponse)
  })
  render(<MCPConfigPanel />)
  await screen.findByText('fixture')
  fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
  await screen.findByText(/读取失败/)
  await waitFor(() => expect((screen.getByRole('button', { name: '添加' }) as HTMLButtonElement).disabled).toBe(true))
})
it('a delete confirmation cannot write the previous config into a replacement connection', async () => {
  restore = configureStudioConnection('http://mcp.fixture', async input => Response.json(String(input).endsWith('/status') ? status : configResponse))
  render(<MCPConfigPanel />)
  fireEvent.click(await screen.findByRole('button', { name: '删除 MCP 服务器 fixture' }))
  await screen.findByRole('button', { name: '删除' })
  const next = vi.fn(async () => Response.json({ success: true, saved: true, commandId: 'save', revision: 1 }))
  await act(async () => { restoreNext = configureStudioConnection('http://next.fixture', next) })
  fireEvent.click(screen.getByRole('button', { name: '删除' }))
  expect(next).not.toHaveBeenCalled()
  expect(screen.getByText('fixture')).toBeTruthy()
})
it('a late enable-state save cannot change the visible confirmed config after reconnection', async () => {
  let resolve!: (response: Response) => void
  restore = configureStudioConnection('http://mcp.fixture', async (input, init) => init?.method === 'PUT' ? new Promise(done => { resolve = done }) : Response.json(String(input).endsWith('/status') ? status : configResponse))
  render(<MCPConfigPanel />)
  fireEvent.click(await screen.findByRole('button', { name: '禁用' }))
  await act(async () => {
    restoreNext = configureStudioConnection('http://next.fixture', async () => Response.json({}))
    resolve(Response.json({ success: true, saved: true, commandId: 'save', revision: 1 }))
  })
  expect(screen.queryByText('已保存')).toBeNull()
  expect(screen.queryByRole('button', { name: '启用' })).toBeNull()
  expect((screen.getByRole('button', { name: '禁用' }) as HTMLButtonElement).disabled).toBe(true)
})
it('explicit rereading after a connection change replaces stale metadata and enables the new config', async () => {
  restore = configureStudioConnection('http://mcp.fixture', async input => Response.json(String(input).endsWith('/status') ? status : configResponse))
  render(<MCPConfigPanel />)
  await screen.findByText('fixture')
  await act(async () => { restoreNext = configureStudioConnection('http://next.fixture', async input => Response.json(String(input).endsWith('/status') ? status : { mcpServers: { next: { command: 'node' } }, revision: 0 })) })
  fireEvent.click(await screen.findByRole('button', { name: '重新读取配置' }))
  await screen.findByText('next')
  expect(screen.queryByText('fixture')).toBeNull()
  expect((screen.getByRole('button', { name: '添加' }) as HTMLButtonElement).disabled).toBe(false)
})
