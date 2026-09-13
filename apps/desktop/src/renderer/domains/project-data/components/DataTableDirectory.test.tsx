import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { DataTableDirectory } from './DataTableDirectory'

type DataTableView = components['schemas']['DataTableView']
const table: DataTableView = { projectId: 'p1', tableId: 't1', name: '客户数据', description: '很长的客户说明', sourceKind: 'local', datasetGeneration: 'g1', tableRevision: 1, identity: { mode: 'system' }, slotDefinitions: [], recordCount: 23, syncSummary: { status: 'notApplicable', pendingCount: 0, unknownCount: 0, lastConfirmedAt: null }, createdAt: '2026-09-13T09:00:00Z', updatedAt: '2026-09-13T10:00:00Z' }
afterEach(cleanup)

it('shows real table facts and keeps open separate from edit', async () => {
  const user = userEvent.setup(); const onOpen = vi.fn(); const onEdit = vi.fn()
  const onImportExcel=vi.fn()
  render(<DataTableDirectory items={[table]} onRetry={vi.fn()} onCreate={vi.fn()} onImportExcel={onImportExcel} onOpen={onOpen} onEdit={onEdit} />)
  expect(screen.getByText('23 条记录')).toBeVisible()
  expect(screen.getByText('本地数据')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '打开客户数据' }))
  await user.click(screen.getByRole('button', { name: '编辑客户数据' }))
  await user.click(screen.getByRole('button', { name: '从 Excel 导入' }))
  expect(onOpen).toHaveBeenCalledWith('t1'); expect(onEdit).toHaveBeenCalledWith('t1'); expect(onImportExcel).toHaveBeenCalledOnce()
})

it('distinguishes loading, empty, filtered empty, and stale error states', async () => {
  const retry = vi.fn(); const props = { items: [] as DataTableView[], onRetry: retry, onCreate: vi.fn(), onImportExcel: vi.fn(), onOpen: vi.fn(), onEdit: vi.fn() }
  const view = render(<DataTableDirectory {...props} loading />)
  expect(screen.getByRole('status')).toHaveTextContent('正在加载数据表')
  view.rerender(<DataTableDirectory {...props} />)
  expect(screen.getByText('还没有数据表')).toBeVisible()
  view.rerender(<DataTableDirectory {...props} hasFilters />)
  expect(screen.getByText('没有匹配的数据表')).toBeVisible()
  view.rerender(<DataTableDirectory {...props} items={[table]} error="刷新失败" />)
  expect(screen.getByText('客户数据')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(retry).toHaveBeenCalledOnce()
})

it('keeps archived tables openable while hiding mutating actions', async () => {
  const onOpen = vi.fn()
  render(<DataTableDirectory items={[table]} readonly onRetry={vi.fn()} onCreate={vi.fn()} onImportExcel={vi.fn()} onOpen={onOpen} onEdit={vi.fn()} />)
  expect(screen.queryByRole('button', { name: '新建数据表' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '从 Excel 导入' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '编辑客户数据' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '打开客户数据' }))
  expect(onOpen).toHaveBeenCalledWith('t1')
})
