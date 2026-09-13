import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const probe = vi.hoisted(() => vi.fn<() => Promise<{ success: boolean }>>())
vi.mock('../api', () => ({ systemApi: { getConfig: probe } }))
import { StudioConnectionNotice } from '../components/StudioConnectionNotice'
beforeEach(() => { probe.mockReset() })
afterEach(cleanup)
const disconnect = () => act(() => { window.dispatchEvent(new Event('studio:connection-error')) })
it('shows repeated failures, keeps the notice after a failed probe and clears only after success', async () => {
  render(<StudioConnectionNotice />)
  expect(screen.queryByRole('alert')).toBeNull()
  disconnect()
  expect(screen.getByRole('alert').textContent).toContain('当前草稿仍保留')
  probe.mockResolvedValueOnce({ success: false }).mockResolvedValueOnce({ success: true })
  fireEvent.click(screen.getByRole('button', { name: '重试连接' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '重试连接' })).toBeDefined())
  expect(screen.getByRole('alert')).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: '重试连接' }))
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  disconnect()
  expect(screen.getByRole('alert')).toBeDefined()
})
it('deduplicates retries and does not let an older successful probe hide a newer failure', async () => {
  let complete!: (result: { success: boolean }) => void
  probe.mockImplementation(() => new Promise(resolve => { complete = resolve }))
  render(<StudioConnectionNotice />)
  disconnect()
  fireEvent.click(screen.getByRole('button', { name: '重试连接' }))
  fireEvent.click(screen.getByRole('button', { name: '正在检查连接' }))
  expect(probe).toHaveBeenCalledOnce()
  disconnect()
  await act(async () => { complete({ success: true }) })
  expect(screen.getByRole('alert')).toBeDefined()
})
