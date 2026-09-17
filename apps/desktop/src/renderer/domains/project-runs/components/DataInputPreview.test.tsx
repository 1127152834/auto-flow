import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { DataInputPreview } from './DataInputPreview'

afterEach(cleanup)

it('shows the two business inputs with their aliases, tables, records and ready result', () => {
  render(<DataInputPreview inputs={[
    { alias: '人员', tableDisplay: '人员资料', recordDisplay: '张三', values: [{ label: '姓名', value: '张三' }], outcome: 'ready' },
    { alias: '邮箱', tableDisplay: '邮箱池', recordDisplay: 'zhangsan@example.com', values: [{ label: '邮箱地址', value: 'zhangsan@example.com' }], outcome: 'ready' },
  ]} />)

  const table = screen.getByRole('table', { name: '数据输入预览结果' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['输入', '数据表', '匹配记录', '冻结字段', '结果'])
  expect(within(table).getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell').map(cell => cell.textContent))).toEqual([
    ['人员', '人员资料', '张三', '姓名：张三', '可以使用'],
    ['邮箱', '邮箱池', 'zhangsan@example.com', '邮箱地址：zhangsan@example.com', '可以使用'],
  ])
})

it.each([
  ['noMatch', '没有匹配记录', 'warning'],
  ['temporarilyBusy', '记录暂时被占用', 'warning'],
  ['ambiguous', '匹配结果不唯一', 'danger'],
  ['configurationError', '配置错误', 'danger'],
  ['scanBudgetExceeded', '扫描范围过大', 'danger'],
  ['notEvaluated', '尚未确定', 'neutral'],
] as const)('presents %s as a distinct business result', (outcome, label, tone) => {
  render(<DataInputPreview inputs={[{ alias: '邮箱', tableDisplay: '邮箱池', recordDisplay: null, outcome }]} />)

  expect(screen.getByText(label)).toHaveAttribute('data-table-status', tone)
  expect(screen.getByRole('cell', { name: '没有可显示的匹配记录' })).toHaveTextContent('—')
})

it('presents a missing optional input as a valid omission instead of a blocking no-match', () => {
  render(<DataInputPreview inputs={[{
    alias: '备用邮箱',
    tableDisplay: '邮箱池',
    recordDisplay: null,
    outcome: 'noMatch',
    required: false,
    scannedCount: 18,
  }]} />)

  expect(screen.getByText('可选输入未找到')).toHaveAttribute('data-table-status', 'neutral')
  expect(screen.getByText('不会阻止本次启动')).toBeInTheDocument()
  expect(screen.getByText('已扫描 18 条记录')).toBeInTheDocument()
  expect(screen.queryByText('没有匹配记录')).not.toBeInTheDocument()
})

it('shows scan facts and actionable detail without losing long text', () => {
  const detail = '当前符合条件的记录全部被其他任务占用，请稍后重试。'.repeat(12)
  render(<DataInputPreview inputs={[{
    alias: '邮箱',
    tableDisplay: '邮箱池',
    recordDisplay: null,
    outcome: 'temporarilyBusy',
    scannedCount: 126,
    detail,
  }]} />)

  expect(screen.getByText('已扫描 126 条记录')).toBeInTheDocument()
  expect(screen.getByText(detail)).toHaveClass('whitespace-pre-wrap', 'break-words')
})

it('announces loading without presenting it as an empty result', () => {
  render(<DataInputPreview inputs={[]} loading />)

  expect(screen.getByRole('table', { name: '数据输入预览结果' })).toHaveAttribute('aria-busy', 'true')
  expect(screen.getByRole('status')).toHaveTextContent('正在预览数据输入')
  expect(screen.queryByText('没有已配置的数据输入')).not.toBeInTheDocument()
})

it('announces a read failure without presenting it as empty data', () => {
  render(<DataInputPreview inputs={[]} error="服务连接已中断，请重新预检。" />)

  expect(screen.getByRole('alert')).toHaveTextContent('数据输入预检失败：服务连接已中断，请重新预检。')
  expect(screen.queryByText('没有已配置的数据输入')).not.toBeInTheDocument()
})

it('uses the shared scrollable fine-grid table and keeps long business text readable', () => {
  const alias = '主要联系人'.repeat(20)
  const tableDisplay = '人员与组织关系明细表'.repeat(20)
  const recordDisplay = '张三｜华东事业部｜重要客户'.repeat(30)
  render(<DataInputPreview inputs={[{ alias, tableDisplay, recordDisplay, outcome: 'ready' }]} />)

  expect(screen.getByRole('region', { name: '数据输入预览表格' })).toHaveClass('af-table-scroll', 'overflow-auto', 'rounded-control')
  expect(screen.getByRole('region', { name: '数据输入预览表格' })).toHaveAttribute('tabindex', '0')
  expect(screen.getByRole('table', { name: '数据输入预览结果' })).toHaveClass('af-table')
  for (const value of [alias, tableDisplay, recordDisplay]) expect(screen.getByText(value)).toHaveClass('break-words')
})
