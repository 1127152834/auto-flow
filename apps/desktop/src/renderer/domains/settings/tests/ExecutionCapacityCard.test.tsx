import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ExecutionCapacityCard } from '../components/ExecutionCapacityCard'
import type { ExecutionSettings, ExecutionSettingsApi } from '../executionApi'

afterEach(cleanup)
const recommended: ExecutionSettings = {
  maxRunningBrowsers: null, recommendedMaxRunningBrowsers: 6, effectiveMaxRunningBrowsers: 6,
  maxLiveBrowsers: 12, memoryPressure: false, hardware: { logicalCpus: 8, totalMemoryGb: 16 }, revision: 0,
}

function api(overrides: Partial<ExecutionSettingsApi> = {}): ExecutionSettingsApi {
  return {
    read: vi.fn(async () => recommended),
    save: vi.fn(async (value: number | null, revision: number) => ({
      ...recommended, maxRunningBrowsers: value, effectiveMaxRunningBrowsers: value ?? 6,
      maxLiveBrowsers: 2 * (value ?? 6), revision: revision + 1,
    })),
    ...overrides,
  }
}

it('explains the recommendation and saves a custom limit with the current revision', async () => {
  const client = api()
  render(<ExecutionCapacityCard api={client} />)
  expect(await screen.findByText(/推荐 6 个（依据：8 个逻辑 CPU、16 GB 内存）/)).toBeInTheDocument()
  const input = screen.getByLabelText('最多同时运行的浏览器')
  expect(input).toHaveValue('6')
  fireEvent.change(input, { target: { value: '10' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(client.save).toHaveBeenCalledWith(10, 0))
  expect(await screen.findByText('当前使用自定义值')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '恢复推荐值' }))
  await waitFor(() => expect(client.save).toHaveBeenLastCalledWith(null, 1))
})

it('rejects values outside 1–64 before calling the service and shows service errors', async () => {
  const client = api({ save: vi.fn(async () => { throw new Error('设置已被修改，请刷新后重试') }) })
  render(<ExecutionCapacityCard api={client} />)
  const input = await screen.findByDisplayValue('6')
  fireEvent.change(input, { target: { value: '65' } })
  expect(screen.getByRole('alert')).toHaveTextContent('请输入 1–64 的整数')
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  fireEvent.change(input, { target: { value: '4' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByText('设置已被修改，请刷新后重试')).toBeInTheDocument()
})
