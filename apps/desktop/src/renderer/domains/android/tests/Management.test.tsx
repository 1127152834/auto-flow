import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { CreateDeviceForm } from '../components/CreateDeviceForm'
import { deviceGroup } from '../model'
import type { AndroidApi, AndroidDevice, AndroidEnvironment } from '../api'

const device: AndroidDevice = { deviceId: 'original', name: '原设备', runtimeId: 'lima', ownerRunId: null, control: 'idle', generation: 1, width: 720, height: 1280, imageId: 'sha256:' + 'a'.repeat(64), androidStatus: 'ready', lastError: null, cpu: 1, memoryMb: 1536, dpi: 320, androidVersion: '13', architecture: 'arm64', dataRetained: false, deleted: false }
const environment: AndroidEnvironment = { available: true, platformSupported: true, message: '运行环境可用', runtimeId: 'lima', cpuCount: 6, memoryMb: 8000, images: [{ id: device.imageId, name: 'Android 13 标准 · ARM64', reference: 'standard' }] }
function api(): AndroidApi { return { create: vi.fn(async () => device), devices: vi.fn(), environment: vi.fn(), operate: vi.fn(), rename: vi.fn(), preview: vi.fn() } }
beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('copy creates a fresh identity and config without copying runtime ownership or data', async () => {
  const client = api(), done = vi.fn()
  render(<CreateDeviceForm source={device} environment={environment} api={client} disabled={false} onCancel={vi.fn()} onCreated={done} />)
  expect(screen.getByText('新实例使用独立空白数据，不复制已安装应用或登录状态。')).toBeVisible()
  await userEvent.click(screen.getByRole('switch', { name: '创建后启动' }))
  await userEvent.click(screen.getByRole('button', { name: '创建实例' }))
  await waitFor(() => expect(done).toHaveBeenCalled())
  const submitted = vi.mocked(client.create).mock.calls[0][0]
  expect(submitted.deviceId).not.toBe(device.deviceId)
  expect(submitted).toMatchObject({ name: '原设备 副本', start: false, width: 720, memoryMb: 1536 })
  expect(submitted).not.toHaveProperty('ownerRunId')
})

it('a lost creation response keeps the same immutable request for an explicit retry', async () => {
  const client = api()
  vi.mocked(client.create).mockRejectedValueOnce(new Error('lost response'))
  render(<CreateDeviceForm environment={environment} api={client} disabled={false} onCancel={vi.fn()} onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('实例名称')).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '按原编号重试创建' }))
  await waitFor(() => expect(client.create).toHaveBeenCalledTimes(2))
  expect(vi.mocked(client.create).mock.calls[0][0]).toEqual(vi.mocked(client.create).mock.calls[1][0])
})

it('busy, stopped and unverified devices are never counted as allocatable', () => {
  expect(deviceGroup(device)).toBe('可分配')
  expect(deviceGroup({ ...device, control: 'manual', ownerRunId: 'run' })).toBe('使用中')
  expect(deviceGroup({ ...device, control: 'recovery_required' })).toBe('启停与待处理')
  expect(deviceGroup({ ...device, androidStatus: 'stopped' })).toBe('启停与待处理')
  expect(deviceGroup({ ...device, androidStatus: 'unknown' })).toBe('启停与待处理')
})
