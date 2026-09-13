import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { DataStatusTable } from './DataStatusTable'

type Schema = components['schemas']
afterEach(cleanup)
const status: Schema['DataStatusView'] = { statusId: 'status-a', name: '待整理', color: '#A86f4c', order: 0, statusRevision: 1 }
const usage = (currentRecords = 0, activeBatchOperations = 0): Schema['DataStatusUsageDirectory'] => ({ datasetGeneration: 'generation-a', calculatedAt: '2026-09-14T00:00:00Z', items: [{ statusId: status.statusId, currentRecords, activeBatchOperations }], configurationReferences: { availability: 'notImplemented' } })
const props = () => ({ statuses: [status], onCreate: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn(), onRetryUsage: vi.fn() })

it('renders the gallery status table with two separate reference columns and only real zero counts', () => {
  render(<DataStatusTable {...props()} usage={usage()} />)
  expect(screen.getByRole('heading', { name: '数据状态', level: 3 })).toBeVisible()
  const table = screen.getByRole('table', { name: '数据状态' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['状态名称', '当前记录', '未完成批量操作', '操作'])
  const row = within(table).getAllByRole('row')[1]
  expect(within(row).getAllByRole('cell').slice(1, 3).map(cell => cell.textContent)).toEqual(['0', '0'])
  expect(screen.getByText(/分别统计，不相加/)).toBeVisible()
  expect(screen.getByRole('button', { name: '删除状态 待整理' })).toBeEnabled()
})

it('passes the original status to actions and does not perform a local deletion', () => {
  const p = props(); render(<DataStatusTable {...p} usage={usage()} />)
  fireEvent.click(screen.getByRole('button', { name: '新增状态' }))
  fireEvent.click(screen.getByRole('button', { name: '编辑状态 待整理' }))
  fireEvent.click(screen.getByRole('button', { name: '删除状态 待整理' }))
  expect(p.onCreate).toHaveBeenCalledTimes(1)
  expect(p.onEdit).toHaveBeenCalledWith(status)
  expect(p.onDelete).toHaveBeenCalledWith(status)
  expect(screen.getByText('待整理')).toBeVisible()
  expect(screen.getByText(/删除前仍需检查影响/)).toBeVisible()
})

it.each([{ current: 3, batches: 0 }, { current: 0, batches: 2 }, { current: 3, batches: 2 }])('blocks deletion for $current records and $batches unfinished batches without summing them', ({ current, batches }) => {
  const p = props(); render(<DataStatusTable {...p} usage={usage(current, batches)} />)
  const row = screen.getAllByRole('row')[1]
  expect(within(row).getAllByRole('cell').slice(1, 3).map(cell => cell.textContent)).toEqual([String(current), String(batches)])
  const remove = screen.getByRole('button', { name: '删除状态 待整理' })
  expect(remove).toBeDisabled()
  expect(remove).toHaveAccessibleDescription(/引用/)
  fireEvent.click(remove)
  expect(p.onDelete).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: '编辑状态 待整理' })).toBeEnabled()
})

it.each([{ flag: 'loading', label: '正在读取…' }, { flag: 'absent', label: '尚未读取' }, { flag: 'missing', label: '待刷新' }, { flag: 'error', label: '引用暂时无法读取' }])('keeps $flag distinct from a known zero and offers a retry', ({ flag, label }) => {
  const p = props()
  render(<DataStatusTable {...p} usage={flag === 'missing' ? { ...usage(), items: [] } : flag === 'error' ? usage() : undefined} loading={flag === 'loading'} error={flag === 'error' ? '读取失败' : null} />)
  const row = screen.getAllByRole('row')[1]
  expect(within(row).getAllByRole('cell').slice(1, 3).map(cell => cell.textContent)).toEqual([label, label])
  expect(screen.getByRole('button', { name: '删除状态 待整理' })).toBeDisabled()
  if (flag !== 'loading') {
    fireEvent.click(screen.getByRole('button', { name: '重新读取引用' }))
    expect(p.onRetryUsage).toHaveBeenCalledTimes(1)
  }
})

it.each(['readonly', 'disabled'] as const)('guards create, edit and delete when %s while preserving readable facts', flag => {
  const p = props(); render(<DataStatusTable {...p} usage={usage()} {...{ [flag]: true }} />)
  for (const name of ['新增状态', '编辑状态 待整理', '删除状态 待整理']) {
    const button = screen.getByRole('button', { name })
    expect(button).toBeDisabled(); fireEvent.click(button)
  }
  expect(p.onCreate).not.toHaveBeenCalled(); expect(p.onEdit).not.toHaveBeenCalled(); expect(p.onDelete).not.toHaveBeenCalled()
  expect(screen.getAllByText('0')).toHaveLength(2)
})

it('updates action admission after new references arrive and after a lock changes', () => {
  const p = props(), view = render(<DataStatusTable {...p} usage={usage()} />)
  view.rerender(<DataStatusTable {...p} usage={usage(1)} />)
  fireEvent.click(screen.getByRole('button', { name: '删除状态 待整理' }))
  expect(p.onDelete).not.toHaveBeenCalled()
  view.rerender(<DataStatusTable {...p} usage={usage()} disabled />)
  expect(screen.getByRole('button', { name: '删除状态 待整理' })).toBeDisabled()
})

it('preserves names and supplied order while rejecting arbitrary CSS colors', () => {
  render(<DataStatusTable {...props()} statuses={[{ ...status, name: '很长的状态名称😀', color: 'url(https://invalid.test/a)' }, { ...status, statusId: 'status-b', name: '已整理', color: '#123456' }]} usage={usage()} />)
  expect(screen.getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell')[0].textContent)).toEqual(['很长的状态名称😀', '已整理'])
  const firstDot = screen.getAllByRole('row')[1].querySelector('[data-status-color]')
  const secondDot = screen.getAllByRole('row')[2].querySelector('[data-status-color]')
  expect(firstDot).not.toHaveAttribute('style')
  expect(secondDot).toHaveStyle({ backgroundColor: '#123456' })
  expect(firstDot).toHaveAttribute('aria-hidden', 'true')
})

it('renders an honest empty state and no synthetic system statuses', () => {
  render(<DataStatusTable {...props()} statuses={[]} usage={{ ...usage(), items: [] }} />)
  expect(screen.getByText('尚未设置数据状态')).toBeVisible()
  expect(screen.queryByText('待整理')).toBeNull()
  expect(screen.getByRole('button', { name: '新增状态' })).toBeEnabled()
})
