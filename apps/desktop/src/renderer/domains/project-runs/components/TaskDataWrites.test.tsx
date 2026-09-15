import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { TaskDataWrites } from './TaskDataWrites'

afterEach(cleanup)

it('shows an explicit email status change and a newly created account stable reference', () => {
  render(<TaskDataWrites writes={[
    { kind: 'statusChange', tableDisplay: '邮箱池', recordDisplay: 'zhangsan@example.com', previousStatus: '待使用', nextStatus: '已使用', outcome: 'succeeded' },
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: '张三的账号', referenceDisplay: '账号记录 #1008', outcome: 'succeeded' },
  ]} />)

  const table = screen.getByRole('table', { name: '任务数据写入结果' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['操作', '数据表与记录', '写入事实', '结果'])
  expect(within(table).getByText('待使用 → 已使用')).toBeVisible()
  expect(within(table).getByText('稳定引用：账号记录 #1008')).toBeVisible()
  expect(within(table).getAllByText('已确认')).toHaveLength(2)
})

it('keeps conflicts and unknown results distinct from confirmed writes', () => {
  render(<TaskDataWrites writes={[
    { kind: 'statusChange', tableDisplay: '邮箱池', recordDisplay: 'zhangsan@example.com', previousStatus: '待使用', nextStatus: '已使用', outcome: 'conflict' },
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: '张三的账号', referenceDisplay: '账号记录 #1008', outcome: 'unknown' },
  ]} />)

  expect(screen.getByText('写入冲突')).toHaveAttribute('data-table-status', 'danger')
  expect(screen.getByText('结果待核对')).toHaveAttribute('data-table-status', 'warning')
  expect(screen.queryByText('已确认')).not.toBeInTheDocument()
})

it('does not turn loading, unread data or a read failure into an empty state', () => {
  const view = render(<TaskDataWrites loading />)
  expect(screen.getByRole('table', { name: '任务数据写入结果' })).toHaveAttribute('aria-busy', 'true')
  expect(screen.getByRole('status')).toHaveTextContent('正在读取任务数据写入')
  expect(screen.queryByText('本任务没有显式数据写入')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites />)
  expect(screen.getByText('任务数据写入尚未读取')).toBeVisible()
  expect(screen.queryByText('本任务没有显式数据写入')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites error="服务暂时不可用" />)
  expect(screen.getByRole('alert')).toHaveTextContent('任务数据写入读取失败：服务暂时不可用')
  expect(screen.queryByText('本任务没有显式数据写入')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites writes={[]} />)
  expect(screen.getByText('本任务没有显式数据写入')).toBeVisible()
})

it('preserves confirmed rows while a refresh fails and never exposes internal identities', () => {
  render(<TaskDataWrites writes={[
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: '张三的账号', referenceDisplay: '账号记录 #1008', outcome: 'succeeded' },
  ]} error="写入事实刷新失败" />)

  expect(screen.getByText('稳定引用：账号记录 #1008')).toBeVisible()
  expect(screen.getByRole('alert')).toBeVisible()
  expect(screen.queryByText(/lease/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/revision/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/[0-9a-f]{8}-[0-9a-f-]{27,}/i)).not.toBeInTheDocument()
  expect(screen.queryByText('本任务没有显式数据写入')).not.toBeInTheDocument()
})

it('compacts UUID-backed references into readable record labels', () => {
  const uuid = 'e97b544d-3b57-424d-ad2f-f166e6119027'
  render(<TaskDataWrites writes={[
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: `uuid · ${uuid}`, referenceDisplay: `uuid · ${uuid}`, outcome: 'succeeded' },
  ]} />)

  expect(screen.getByText('记录 · e97b544d…9027')).toBeVisible()
  expect(screen.getByText('稳定引用：记录 · e97b544d…9027')).toBeVisible()
  expect(screen.queryByText(uuid, { exact: false })).not.toBeInTheDocument()
})

it('uses the shared scrollable fine-grid table and wraps long values', () => {
  const tableDisplay = '跨区域账号归档数据表'.repeat(20)
  const recordDisplay = '张三的企业级账号及长期业务说明'.repeat(25)
  const referenceDisplay = '账号记录｜企业客户｜2026-09'.repeat(20)
  render(<TaskDataWrites writes={[{ kind: 'recordCreated', tableDisplay, recordDisplay, referenceDisplay, outcome: 'succeeded' }]} />)

  expect(screen.getByRole('region', { name: '任务数据写入表格' })).toHaveClass('af-table-scroll', 'overflow-auto', 'rounded-control')
  expect(screen.getByRole('table', { name: '任务数据写入结果' })).toHaveClass('af-table')
  expect(screen.getByText(tableDisplay)).toHaveClass('break-words')
  expect(screen.getByText(recordDisplay)).toHaveClass('break-words')
  expect(screen.getByText(`稳定引用：${referenceDisplay}`)).toHaveClass('break-words')
})
