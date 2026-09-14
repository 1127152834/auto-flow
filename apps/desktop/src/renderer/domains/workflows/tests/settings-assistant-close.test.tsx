import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { executeClientAction } from '../api/aiAssistantSkills'
import { credentialApi } from '../api'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
const close = vi.fn()
beforeEach(() => { close.mockReset(); setStudioTransport(mockRequest) })
afterEach(() => { cleanup(); setStudioTransport(mockRequest); vi.restoreAllMocks() })
async function edit() {
  render(<GlobalConfigDialog isOpen onClose={close} />)
  fireEvent.click(screen.getByRole('button', { name: '凭据库' }))
  fireEvent.click(await screen.findByRole('button', { name: '新增凭据' }))
  fireEvent.change(screen.getByPlaceholderText('如：我的邮箱'), { target: { value: 'assistant-close-fixture' } })
}
it.each(['取消','放弃修改','保存后继续'])('AI close waits for %s before reporting its result', async choice => {
  await edit()
  let settled = false
  let pending!: ReturnType<typeof executeClientAction>
  await act(async () => { pending = executeClientAction('close_global_config').then(result => { settled = true; return result }) })
  const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  expect(settled).toBe(false)
  expect(close).not.toHaveBeenCalled()
  fireEvent.click(within(dialog).getByRole('button', { name: choice }))
  const result = await pending
  expect(result.success).toBe(choice !== '取消')
  expect(close).toHaveBeenCalledTimes(choice === '取消' ? 0 : 1)
})
it('AI close does not report success after rejected saving', async () => {
  await edit()
  vi.spyOn(credentialApi, 'upsert').mockResolvedValue({ success: false, error: '写入失败' })
  let pending!: ReturnType<typeof executeClientAction>
  await act(async () => { pending = executeClientAction('close_global_config') })
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存凭据编辑？' })).getByRole('button', { name: '保存后继续' }))
  await screen.findByText('保存失败：写入失败')
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  expect((await pending).success).toBe(false)
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('value','assistant-close-fixture')
})
it('AI close reports unavailable when no settings owner is mounted', async () => {
  expect((await executeClientAction('close_global_config')).success).toBe(false)
})
it('AI close succeeds for an already closed settings owner', async () => {
  render(<GlobalConfigDialog isOpen={false} onClose={close} />)
  expect((await executeClientAction('close_global_config')).success).toBe(true)
  expect(close).not.toHaveBeenCalled()
})
it('unmounting during a pending decision cannot falsely confirm AI close', async () => {
  await edit()
  let pending!: ReturnType<typeof executeClientAction>
  await act(async () => { pending = executeClientAction('close_global_config') })
  await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  cleanup()
  expect((await pending).success).toBe(false)
  expect(close).not.toHaveBeenCalled()
})
it('a second AI close is rejected while the original decision is pending', async () => {
  await edit()
  let pending!: ReturnType<typeof executeClientAction>
  await act(async () => { pending = executeClientAction('close_global_config') })
  const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  expect((await executeClientAction('close_global_config')).success).toBe(false)
  fireEvent.click(within(dialog).getByRole('button', { name: '取消' }))
  await waitFor(async () => expect((await pending).success).toBe(false))
})
it('unmounting a save failure alert releases the waiting AI command as unsuccessful', async () => {
  await edit()
  vi.spyOn(credentialApi, 'upsert').mockResolvedValue({ success: false, error: '不可写' })
  let pending!: ReturnType<typeof executeClientAction>
  await act(async () => { pending = executeClientAction('close_global_config') })
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存凭据编辑？' })).getByRole('button', { name: '保存后继续' }))
  await screen.findByText('保存失败：不可写')
  cleanup()
  expect((await pending).success).toBe(false)
  expect(close).not.toHaveBeenCalled()
})
