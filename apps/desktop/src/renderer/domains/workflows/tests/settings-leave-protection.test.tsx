import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
const close = vi.fn()
let saves = 0
beforeEach(() => { close.mockReset(); saves = 0; setStudioTransport(async (input, init) => {
  if (String(input).endsWith('/credentials') && init?.method === 'POST') saves++
  return mockRequest(input, init)
}) })
afterEach(() => { cleanup(); setStudioTransport(mockRequest) })
async function edit() {
  render(<GlobalConfigDialog isOpen onClose={close} />)
  fireEvent.click(screen.getByRole('button', { name: '凭据库' }))
  fireEvent.click(await screen.findByRole('button', { name: '新增凭据' }))
  fireEvent.change(screen.getByPlaceholderText('如：我的邮箱'), { target: { value: 'leave-fixture' } })
  fireEvent.change(screen.getByPlaceholderText('值'), { target: { value: 'dummy-only' } })
}
const leaveThrough = (target: string) => fireEvent.click(target === '背景' ? screen.getByTestId('global-config-backdrop') : screen.getByRole('button', { name: target }))
for (const target of ['系统', '完成保存', '关闭全局配置', '背景']) {
  it(`${target}: cancel keeps unsaved credential input`, async () => {
    await edit()
    leaveThrough(target)
    const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
    fireEvent.click(within(dialog).getByRole('button', { name: '取消' }))
    expect(close).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-only')
    expect(saves).toBe(0)
  })
  it(`${target}: save confirms before leaving`, async () => {
    await edit()
    leaveThrough(target)
    const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
    fireEvent.click(within(dialog).getByRole('button', { name: '保存后继续' }))
    await waitFor(() => expect(saves).toBe(1))
    if (target === '系统') await screen.findByText('配置系统相关的全局设置')
    else await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
  })
  it(`${target}: discard leaves without a write`, async () => {
    await edit()
    leaveThrough(target)
    const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
    fireEvent.click(within(dialog).getByRole('button', { name: '放弃修改' }))
    if (target === '系统') await screen.findByText('配置系统相关的全局设置')
    else await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
    expect(saves).toBe(0)
  })
}
it('failed save prevents leaving and retains the entered value', async () => {
  await edit()
  // Keep the same transport epoch; the server response fails, not the connection.
  const { credentialApi } = await import('../api')
  const spy = vi.spyOn(credentialApi, 'upsert').mockResolvedValue({ success: false, error: '不可写' })
  try {
    fireEvent.click(screen.getByRole('button', { name: '完成保存' }))
    fireEvent.click(within(await screen.findByRole('dialog', { name: '保存凭据编辑？' })).getByRole('button', { name: '保存后继续' }))
    await screen.findByText('保存失败：不可写')
    expect(close).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-only')
  } finally { spy.mockRestore() }
})
it('same active tab does not ask to discard its own form', async () => {
  await edit()
  fireEvent.click(screen.getByRole('button', { name: '凭据库' }))
  expect(screen.queryByRole('dialog', { name: '保存凭据编辑？' })).toBeNull()
  expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-only')
})

let sequence = 0
async function editWebdav() {
  render(<GlobalConfigDialog isOpen onClose={close} />)
  fireEvent.click(screen.getByRole('button', { name: '存储' }))
  const field = await screen.findByPlaceholderText('子目录（可选），如 workflows')
  const value = `leave-webdav-${++sequence}`
  fireEvent.change(field, { target: { value } })
  return value
}
for (const target of ['系统', '完成保存', '关闭全局配置', '背景']) {
  for (const choice of ['取消', '保存后继续', '放弃修改']) {
    it(`WebDAV ${target}: ${choice} preserves the configured leave order`, async () => {
      const value = await editWebdav()
      let writes = 0
      const { apiRequest } = await import('../api')
      // Observe requests without replacing the service epoch.
      const api = await import('../api')
      const spy = vi.spyOn(api, 'apiRequest').mockImplementation(async (...args) => {
        if (args[0] === '/local-workflows/webdav-config' && args[1]?.method === 'POST') writes++
        return apiRequest(...args)
      })
      try {
        leaveThrough(target)
        const dialog = await screen.findByRole('dialog', { name: '保存 WebDAV 配置？' })
        fireEvent.click(within(dialog).getByRole('button', { name: choice }))
        if (choice === '取消') {
          expect(close).not.toHaveBeenCalled()
          expect(screen.getByPlaceholderText('子目录（可选），如 workflows')).toHaveProperty('value', value)
        } else if (target === '系统') await screen.findByText('配置系统相关的全局设置')
        else await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
        expect(writes).toBe(choice === '保存后继续' ? 1 : 0)
      } finally { spy.mockRestore() }
    })
  }
}
it('WebDAV failed save keeps the form open', async () => {
  const value = await editWebdav()
  const api = await import('../api')
  const original = api.apiRequest
  const spy = vi.spyOn(api, 'apiRequest').mockImplementation(async (...args) => args[0] === '/local-workflows/webdav-config' && args[1]?.method === 'POST' ? { success: false, error: '磁盘不可写' } : original(...args))
  try {
    leaveThrough('完成保存')
    fireEvent.click(within(await screen.findByRole('dialog', { name: '保存 WebDAV 配置？' })).getByRole('button', { name: '保存后继续' }))
    await screen.findByText('磁盘不可写')
    expect(close).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('子目录（可选），如 workflows')).toHaveProperty('value', value)
  } finally { spy.mockRestore() }
})
it('WebDAV successful save clears dirty state without an extra prompt', async () => {
  await editWebdav()
  fireEvent.click(screen.getByRole('button', { name: '保存配置' }))
  await screen.findByText('已保存模拟配置，未连接远程存储')
  leaveThrough('完成保存')
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
  expect(screen.queryByRole('dialog', { name: '保存 WebDAV 配置？' })).toBeNull()
})
it('a repeated leave click cannot replace the pending destination or duplicate saving', async () => {
  await edit()
  leaveThrough('完成保存')
  leaveThrough('系统')
  const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  expect((screen.getByPlaceholderText('值') as HTMLInputElement).closest('fieldset')?.disabled).toBe(true)
  fireEvent.click(within(dialog).getByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
  expect(saves).toBe(1)
})
it('Escape cancels the leave decision and restores editing', async () => {
  await edit()
  leaveThrough('完成保存')
  await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  fireEvent.keyDown(window, { key: 'Escape' })
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '保存凭据编辑？' })).toBeNull())
  expect(close).not.toHaveBeenCalled()
  expect((screen.getByPlaceholderText('值') as HTMLInputElement).closest('fieldset')?.disabled).toBe(false)
})
it('unmount cancels a pending leave without later invoking its destination', async () => {
  await edit()
  leaveThrough('完成保存')
  await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  cleanup()
  await Promise.resolve()
  expect(close).not.toHaveBeenCalled()
})
it('an active credential write blocks closing until it is confirmed', async () => {
  await edit()
  const api = await import('../api')
  let resolve!: (value: { success: true; data: { success: true; name: string; mock: boolean | null } }) => void
  const spy = vi.spyOn(api.credentialApi, 'upsert').mockImplementation(() => new Promise(done => { resolve = done }))
  try {
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    leaveThrough('完成保存')
    expect(close).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog', { name: '保存凭据编辑？' })).toBeNull()
    resolve({ success: true, data: { success: true, name: 'leave-fixture', mock: true } })
    await waitFor(() => expect(screen.queryByPlaceholderText('值')).toBeNull())
    expect(close).not.toHaveBeenCalled()
    leaveThrough('完成保存')
    await waitFor(() => expect(close).toHaveBeenCalledTimes(1))
  } finally { spy.mockRestore() }
})
it('connection change during the leave decision prevents saving to the new service', async () => {
  await edit()
  leaveThrough('完成保存')
  const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  const { configureStudioConnection } = await import('../api/config')
  const fetcher = vi.fn(async () => Response.json({ success: true }))
  const restore = configureStudioConnection('http://next.fixture', fetcher)
  try {
    fireEvent.click(within(dialog).getByRole('button', { name: '保存后继续' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '保存凭据编辑？' })).toBeNull())
    expect(close).not.toHaveBeenCalled()
    expect(fetcher).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-only')
  } finally { restore() }
})

it('WebDAV connection change during confirmation never submits the original config to a new service', async () => {
  await editWebdav()
  leaveThrough('完成保存')
  const dialog = await screen.findByRole('dialog', { name: '保存 WebDAV 配置？' })
  const { configureStudioConnection } = await import('../api/config')
  const fetcher = vi.fn(async () => Response.json({ success: true, mock: true }))
  const restore = configureStudioConnection('http://new-webdav.fixture', fetcher)
  try {
    fireEvent.click(within(dialog).getByRole('button', { name: '保存后继续' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '保存 WebDAV 配置？' })).toBeNull())
    expect(fetcher).not.toHaveBeenCalled()
    expect(close).not.toHaveBeenCalled()
    await screen.findByText('连接已更换，请重新读取配置')
  } finally { restore() }
})
