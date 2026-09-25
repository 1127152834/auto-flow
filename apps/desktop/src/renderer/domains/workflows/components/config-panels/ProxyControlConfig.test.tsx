import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { ProxyControlConfig } from './ProxyControlConfig'
import type { NodeData } from '../../editor-store'
const request = vi.hoisted(() => vi.fn())
vi.mock('../../api', () => ({ apiRequest: request }))
afterEach(cleanup)
beforeEach(() => { request.mockReset(); request.mockResolvedValue({ success: true, data: { items: [], matched_count: 0 } }) })
test('shows editable defaults and preserves variable strings', async () => {
  const change = vi.fn()
  render(<ProxyControlConfig data={{ label: '代理', moduleType: 'proxy_change_ip' } as NodeData} onChange={change} />)
  expect((screen.getByLabelText('最大尝试次数（包含首次）') as HTMLInputElement).value).toBe('5')
  fireEvent.change(screen.getByLabelText('重试间隔（秒）'), { target: { value: '{delay}' } })
  expect(change).toHaveBeenCalledWith('retryIntervalSeconds', '{delay}')
  fireEvent.change(screen.getByLabelText('失败处理'), { target: { value: 'capture' } })
  expect(change).toHaveBeenCalledWith('failureMode', 'capture')
  expect(await screen.findByText('保留页面和登录上下文；切换可能中断已有网络请求。')).toBeTruthy()
})
test('loads actual catalog and keeps selected ids', async () => {
  request.mockImplementation(async (path: string) => ({ success: true, data: { matched_count: 1, items: path.includes('locations')
    ? [{ id: 'loc-1', city: 'Dallas', country: 'US', availability: 'available' }]
    : [{ id: 'proxy-1', name: '代理一', connection_id: 'conn-1' }] } }))
  const change = vi.fn()
  render(<ProxyControlConfig data={{ label: '代理', moduleType: 'proxy_change_location', target: 'specified', proxyId: 'proxy-1' } as NodeData} onChange={change} />)
  expect(await screen.findByRole('option', { name: '代理一' })).toBeTruthy()
  expect(await screen.findByRole('option', { name: /Dallas/ })).toBeTruthy()
  fireEvent.change(screen.getByLabelText('地点目录'), { target: { value: 'loc-1' } })
  expect(change).toHaveBeenCalledWith('locationId', 'loc-1')
})
test('query hides retries and displays directory failure', async () => {
  request.mockResolvedValue({ success: false, error: '目录读取失败' })
  render(<ProxyControlConfig data={{ label: '代理', moduleType: 'proxy_query' } as NodeData} onChange={vi.fn()} />)
  expect(screen.queryByLabelText('最大尝试次数（包含首次）')).toBeNull()
  expect((await screen.findByRole('alert')).textContent).toContain('目录读取失败')
  expect(screen.getByLabelText('原操作 ID（可选）')).toBeTruthy()
})
