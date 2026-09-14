import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const storage = vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  return data
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { mcpApi } from '../api/mcp'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
const close = vi.fn()
let writes = 0
beforeEach(() => {
  close.mockReset(); storage.clear(); writes = 0
  setStudioTransport(async (input, init) => { if (String(input).endsWith('/mcp/config') && init?.method === 'PUT') writes++; return mockRequest(input, init) })
})
afterEach(() => { cleanup(); setStudioTransport(mockRequest); vi.restoreAllMocks() })
async function edit() {
  render(<GlobalConfigDialog isOpen onClose={close} />)
  fireEvent.click(screen.getByRole('button', { name: 'MCP' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '添加' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '添加' }))
  fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'), { target: { value: 'mcp-leave-fixture' } })
  fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'), { target: { value: 'node' } })
}
const leaveThrough = (target: string) => {
  if (target === '编辑背景') fireEvent.click(screen.getByTestId('mcp-edit-backdrop'))
  else if (target === '配置背景') fireEvent.click(screen.getByTestId('global-config-backdrop'))
  else if (target === '取消') fireEvent.click(within(screen.getByRole('dialog', { name: '添加 MCP 服务器' })).getByRole('button', { name: '取消' }))
  else fireEvent.click(screen.getByRole('button', { name: target }))
}
for (const target of ['关闭 MCP 编辑','取消','编辑背景','系统','关闭全局配置','完成保存','配置背景']) {
  for (const choice of ['取消','放弃修改','保存后继续']) {
    it(`${target} + ${choice} respects the unsaved MCP draft`, async () => {
      await edit()
      leaveThrough(target)
      const dialog = await screen.findByRole('dialog', { name: '保存 MCP 编辑？' })
      fireEvent.click(within(dialog).getByRole('button', { name: choice }))
      if (choice === '取消') {
        expect(close).not.toHaveBeenCalled()
        expect(screen.getByPlaceholderText('例如 filesystem / weather / github')).toHaveProperty('value','mcp-leave-fixture')
      } else if (target === '系统') await screen.findByText('配置系统相关的全局设置')
      else if (['关闭全局配置','完成保存','配置背景'].includes(target)) await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
      else await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加 MCP 服务器' })).toBeNull())
      expect(writes).toBe(choice === '保存后继续' ? 1 : 0)
    })
  }
}
it('save failure keeps MCP editing and prevents closing the parent', async () => {
  await edit()
  vi.spyOn(mcpApi, 'save').mockResolvedValue({ success: false, error: '不可写' })
  leaveThrough('完成保存')
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存 MCP 编辑？' })).getByRole('button', { name: '保存后继续' }))
  await screen.findByText(/保存失败：不可写/)
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByPlaceholderText('例如 filesystem / weather / github')).toHaveProperty('value','mcp-leave-fixture')
})
it('save-and-leave validates a missing command rather than bypassing the disabled save button', async () => {
  await edit()
  fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'), { target: { value: '' } })
  leaveThrough('完成保存')
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存 MCP 编辑？' })).getByRole('button', { name: '保存后继续' }))
  await screen.findByText('启动命令不能为空')
  expect(writes).toBe(0)
  expect(close).not.toHaveBeenCalled()
})
it('ordinary save still closes the editor after acknowledgement', async () => {
  await edit()
  fireEvent.click(within(screen.getByRole('dialog', { name: '添加 MCP 服务器' })).getByRole('button', { name: '保存' }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '添加 MCP 服务器' })).toBeNull())
  expect(writes).toBe(1)
  await screen.findByText('mcp-leave-fixture')
})
