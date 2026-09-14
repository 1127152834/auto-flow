// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RetentionSettings } from '../components/RetentionSettings'
import { retentionApi } from '../api'
import { retentionDefaults } from '../lib/retentionContract'
import { setStudioTransport } from '../api/transport'
import type { SettingsLeaveGuard } from '../hooks/useSettingsDraftProtection'
const usage = { recordings: { count: 0, sizeMB: 0 }, data: { count: 0, sizeMB: 0 } }
let guard: SettingsLeaveGuard | null
const register = (value: SettingsLeaveGuard | null) => { guard = value }
beforeEach(() => {
  guard = null
  vi.spyOn(retentionApi, 'getConfig').mockResolvedValue({ success: true, data: { success: true, mock: true, config: { ...retentionDefaults }, usage } })
  vi.spyOn(retentionApi, 'setConfig').mockImplementation(async config => ({ success: true, data: { success: true, mock: true, config } }))
  vi.spyOn(retentionApi, 'cleanup').mockResolvedValue({ success: true, data: { success: true, mock: true, recordings: { removed: 0, freedMB: 0 }, data: { removed: 0, freedMB: 0 } } })
  vi.spyOn(retentionApi, 'usage').mockResolvedValue({ success: true, data: { success: true, mock: true, usage } })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })
async function open() { render(<RetentionSettings registerLeaveGuard={register} />); return screen.findByLabelText('录像保留天数') }
it.each(['', '-1', '0.5'])('rejects invalid numeric text %s and keeps input', async value => {
  const field = await open(); fireEvent.change(field, { target: { value } }); fireEvent.click(screen.getByRole('button', { name: '保存策略' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('非负安全整数'))
  expect(retentionApi.setConfig).not.toHaveBeenCalled(); expect(field).toHaveProperty('value', value)
})
it('rejects zero cleanup interval', async () => {
  await open(); fireEvent.change(screen.getByLabelText('清理间隔(小时)'), { target: { value: '0' } }); fireEvent.click(screen.getByRole('button', { name: '保存策略' }))
  await screen.findByRole('alert'); expect(retentionApi.setConfig).not.toHaveBeenCalled()
})
it('offers retry on read failure', async () => {
  vi.mocked(retentionApi.getConfig).mockResolvedValueOnce({ success: false, error: '离线' })
  render(<RetentionSettings />); await screen.findByText('离线'); fireEvent.click(screen.getByRole('button', { name: '重试读取' })); await screen.findByLabelText('录像保留天数')
})
it('does not report failed cleanup as success', async () => {
  vi.mocked(retentionApi.cleanup).mockResolvedValue({ success: false, error: '磁盘不可写' }); await open(); fireEvent.click(screen.getByRole('button', { name: '立即清理一次' }))
  await screen.findByText('磁盘不可写'); expect(screen.queryByRole('status')).toBeNull(); expect(retentionApi.usage).not.toHaveBeenCalled()
})
it('makes Mock cleanup limitations explicit', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: '立即清理一次' })); await screen.findByText('Mock 清理确认：未删除任何真实文件')
})
it.each(['取消', '放弃修改', '保存后继续'])('protects dirty form through %s', async choice => {
  const field = await open(); fireEvent.change(field, { target: { value: '17' } })
  let leaving!: Promise<boolean>; act(() => { leaving = guard!() })
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存留存策略？' })).getByRole('button', { name: choice }))
  expect(await leaving).toBe(choice !== '取消')
  expect(retentionApi.setConfig).toHaveBeenCalledTimes(choice === '保存后继续' ? 1 : 0)
})
it('failed leave-save retains inputs and blocks closing', async () => {
  vi.mocked(retentionApi.setConfig).mockResolvedValue({ success: false, error: '停写' })
  const field = await open(); fireEvent.change(field, { target: { value: '17' } })
  let leaving!: Promise<boolean>; act(() => { leaving = guard!() })
  fireEvent.click(within(await screen.findByRole('dialog', { name: '保存留存策略？' })).getByRole('button', { name: '保存后继续' }))
  expect(await leaving).toBe(false); expect(field).toHaveProperty('value', '17'); await screen.findByText('停写')
})
it('serializes writes and disallows cleanup of dirty settings', async () => {
  let finish!: (value: Awaited<ReturnType<typeof retentionApi.setConfig>>) => void
  vi.mocked(retentionApi.setConfig).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const field = await open(); fireEvent.change(field, { target: { value: '17' } }); fireEvent.click(screen.getByRole('button', { name: '立即清理一次' })); expect(retentionApi.cleanup).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '保存策略' })); fireEvent.click(screen.getByRole('button', { name: '保存策略' })); expect(retentionApi.setConfig).toHaveBeenCalledTimes(1)
  expect(await guard!()).toBe(false)
  await act(async () => finish({ success: false, error: 'fixture failure' }))
})
it('connection changes reject old-draft writes and late save receipts', async () => {
  let finish!: (value: Awaited<ReturnType<typeof retentionApi.setConfig>>) => void
  vi.mocked(retentionApi.setConfig).mockReturnValue(new Promise(resolve => { finish = resolve }))
  const field = await open(); fireEvent.change(field, { target: { value: '17' } }); fireEvent.click(screen.getByRole('button', { name: '保存策略' }))
  let restore!: () => void; act(() => { restore = setStudioTransport(async () => Response.json({})) })
  await act(async () => finish({ success: true, data: { success: true, mock: true, config: retentionDefaults } }))
  expect(field).toHaveProperty('value', '17'); expect(screen.queryByRole('status')).toBeNull()
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('服务连接已变更'))
  act(() => restore())
})
it('successful save leaves clean without another prompt', async () => {
  const field = await open(); fireEvent.change(field, { target: { value: '17' } }); fireEvent.click(screen.getByRole('button', { name: '保存策略' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Mock 策略已保存')); expect(await guard!()).toBe(true)
})
it('preserves confirmed cleanup when usage refresh fails', async () => {
  vi.mocked(retentionApi.usage).mockResolvedValue({ success: false, error: '读取失败' })
  await open(); fireEvent.click(screen.getByRole('button', { name: '立即清理一次' }))
  await screen.findByText('Mock 清理确认：未删除任何真实文件'); await screen.findByText('清理已确认，但用量刷新失败：读取失败')
})
it('reports thrown save errors without losing the draft', async () => {
  vi.mocked(retentionApi.setConfig).mockRejectedValue(new Error('连接关闭'))
  const field = await open(); fireEvent.change(field, { target: { value: '17' } }); fireEvent.click(screen.getByRole('button', { name: '保存策略' }))
  await screen.findByText('连接关闭'); expect(field).toHaveProperty('value', '17'); expect(screen.queryByRole('status')).toBeNull()
})
it('does not install a late initial read from another connection', async () => {
  let finish!: (value: Awaited<ReturnType<typeof retentionApi.getConfig>>) => void
  vi.mocked(retentionApi.getConfig).mockReturnValue(new Promise(resolve => { finish = resolve }))
  render(<RetentionSettings />)
  let restore!: () => void; act(() => { restore = setStudioTransport(async () => Response.json({})) })
  await act(async () => finish({ success: true, data: { success: true, mock: true, config: retentionDefaults, usage } }))
  expect(screen.queryByLabelText('录像保留天数')).toBeNull(); expect(screen.getByRole('button', { name: '重试读取' })).toBeTruthy()
  act(() => restore())
})
