import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ManualItem } from '../../environments/api'
import { ManualItemDirectory, type ManualItemFilters, type ManualItemPage } from './ManualItemDirectory'

const projectId = '00000000-0000-4000-8000-000000000001'
const item = (over: Partial<ManualItem> = {}): ManualItem => ({
  manualItemId: '00000000-0000-4000-8000-00000000000d',
  projectId,
  taskId: '00000000-0000-4000-8000-00000000000e',
  runId: '00000000-0000-4000-8000-00000000000c',
  instanceId: '00000000-0000-4000-8000-00000000000a',
  checkpointRevision: 3,
  status: 'waiting',
  statusRevision: 2,
  expiresAt: new Date(Date.now() + 13 * 60_000).toISOString(),
  allowedTargets: [],
  resumeStarted: false,
  reason: '需要核对提取的标题与日期',
  createdAt: '2026-09-18T05:00:00Z',
  updatedAt: '2026-09-18T05:00:00Z',
  ...over,
} as ManualItem)

const defaultFilters: ManualItemFilters = { q: null, status: 'waiting', sort: 'expiresAt' }

function renderDirectory(options: { page?: ManualItemPage; filters?: ManualItemFilters; loading?: boolean; error?: string } = {}) {
  const onFiltersChange = vi.fn(), onPageChange = vi.fn(), onOpen = vi.fn(), onOpenTask = vi.fn(), onOpenBatch = vi.fn(), onRetry = vi.fn()
  render(<ManualItemDirectory page={options.page} filters={options.filters ?? defaultFilters} loading={options.loading} error={options.error} onFiltersChange={onFiltersChange} onPageChange={onPageChange} onOpen={onOpen} onOpenTask={onOpenTask} onOpenBatch={onOpenBatch} onRetry={onRetry}/>)
  return { onFiltersChange, onPageChange, onOpen, onOpenTask, onOpenBatch, onRetry }
}

afterEach(cleanup)

it('renders the approved four columns with real retention facts', () => {
  renderDirectory({ page: { items: [item()], page: 1, pageSize: 50, total: 1 } })
  for (const column of ['等待原因', '所属任务', '剩余保留时间', '操作']) expect(screen.getByRole('columnheader', { name: column })).toBeVisible()
  expect(screen.getByText('需要核对提取的标题与日期')).toBeVisible()
  expect(screen.getByText('等待处理', { selector: '[data-table-status]' })).toBeVisible()
  expect(screen.getByText('13 分钟')).toBeVisible()
  expect(screen.getByText('共 1 项 · 保留时间以服务端记录为准。')).toBeVisible()
})

it('searches only on submit and keeps the query untouched while typing', () => {
  const { onFiltersChange } = renderDirectory({ page: { items: [item()], page: 1, pageSize: 50, total: 1 } })
  const input = screen.getByLabelText('搜索等待人工事项')
  fireEvent.change(input, { target: { value: '温室' } })
  expect(onFiltersChange).not.toHaveBeenCalled()
  fireEvent.submit(screen.getByRole('search'))
  expect(onFiltersChange).toHaveBeenCalledWith({ ...defaultFilters, q: '温室' })
})

it('offers status, retention sorting and pagination through the existing filters', () => {
  const { onPageChange } = renderDirectory({ page: { items: [item()], page: 2, pageSize: 50, total: 120 } })
  expect(screen.getByLabelText('等待人工状态筛选')).toHaveAttribute('data-choice-value', 'waiting')
  expect(screen.getByLabelText('等待人工排序')).toHaveAttribute('data-choice-value', 'expiresAt')
  screen.getByRole('button', { name: '下一页' }).click()
  expect(onPageChange).toHaveBeenCalledWith(3)
})

it('routes every entry to its real target instead of a synthetic identifier', () => {
  const { onOpen, onOpenTask, onOpenBatch } = renderDirectory({ page: { items: [item()], page: 1, pageSize: 50, total: 1 } })
  screen.getByRole('button', { name: /查看事项/ }).click()
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ manualItemId: '00000000-0000-4000-8000-00000000000d' }))
  screen.getByRole('button', { name: /查看任务/ }).click()
  expect(onOpenTask).toHaveBeenCalledWith('00000000-0000-4000-8000-00000000000e')
  screen.getByRole('button', { name: /查看批次/ }).click()
  expect(onOpenBatch).toHaveBeenCalledWith('00000000-0000-4000-8000-00000000000c')
})

it('separates an empty directory from a failed read and keeps the last page on refresh failure', () => {
  const first = renderDirectory({ page: undefined })
  expect(screen.getByText('当前没有等待人工处理的事项。')).toBeVisible()
  cleanup()
  renderDirectory({ page: undefined, error: '读取内容失败，请重试' })
  expect(screen.getByRole('alert')).toHaveTextContent('等待人工事项读取失败：读取内容失败，请重试')
  expect(screen.queryByText('当前没有等待人工处理的事项。')).not.toBeInTheDocument()
  cleanup()
  // 刷新失败必须保留上次读取的内容，不能把已知数据显示成空
  renderDirectory({ page: { items: [item()], page: 1, pageSize: 50, total: 1 }, error: '读取内容失败，请重试' })
  expect(screen.getByText('需要核对提取的标题与日期')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('刷新失败，当前显示上次读取的等待人工事项：读取内容失败，请重试')
  expect(first.onRetry).not.toHaveBeenCalled()
})
