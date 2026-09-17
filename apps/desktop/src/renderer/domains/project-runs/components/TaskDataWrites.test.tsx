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

  const table = screen.getByRole('table', { name: '项目数据操作结果' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['操作', '数据表与对象', '操作事实', '稳定引用', '结果'])
  expect(within(table).getByText('待使用 → 已使用')).toBeVisible()
  expect(within(table).getByText('账号记录 #1008')).toBeVisible()
  expect(within(table).getAllByText('已确认')).toHaveLength(2)
})

it('shows every supported project data operation with before and after evidence', () => {
  render(<TaskDataWrites writes={[
    { kind: 'query', tableDisplay: '人员表', recordDisplay: '命中 2 条', detail: '筛选：状态为可使用', outcome: 'succeeded' },
    { kind: 'read', tableDisplay: '人员表', recordDisplay: '人员 P001', referenceDisplay: '人员记录 P001', detail: '读取姓名、地区', outcome: 'succeeded' },
    { kind: 'recordUpdated', tableDisplay: '邮箱表', recordDisplay: 'mail-001', referenceDisplay: '邮箱记录 mail-001', beforeSummary: '备注：未验证', afterSummary: '备注：已验证', outcome: 'succeeded' },
    { kind: 'recordDeleted', tableDisplay: '邮箱表', recordDisplay: 'mail-002', referenceDisplay: '邮箱记录 mail-002', beforeSummary: '状态：已停用', outcome: 'succeeded' },
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: 'account-001', referenceDisplay: '账号记录 account-001', afterSummary: '用户名：greenhouse', outcome: 'succeeded' },
    { kind: 'fieldAdded', tableDisplay: '账号表', recordDisplay: '登录结果', referenceDisplay: '字段 登录结果', afterSummary: '文本 · 可选', outcome: 'succeeded' },
    { kind: 'fieldEnsured', tableDisplay: '账号表', recordDisplay: '邮箱', referenceDisplay: '字段 邮箱', detail: '字段已存在，无需变更', outcome: 'succeeded' },
    { kind: 'fieldModified', tableDisplay: '账号表', recordDisplay: '备注', referenceDisplay: '字段 备注', beforeSummary: '可选文本', afterSummary: '必填文本 · 默认值：待补充', outcome: 'succeeded' },
  ]} />)

  const table = screen.getByRole('table', { name: '项目数据操作结果' })
  for (const label of ['查询记录', '读取记录', '编辑记录', '删除记录', '新增记录', '新增字段', '确保字段', '修改字段']) {
    expect(within(table).getByText(label)).toBeVisible()
  }
  expect(within(table).getByText('备注：未验证 → 备注：已验证')).toBeVisible()
  expect(within(table).getByText('状态：已停用 → 已删除')).toBeVisible()
  expect(within(table).getByText('新增后：用户名：greenhouse')).toBeVisible()
  expect(within(table).getByText('可选文本 → 必填文本 · 默认值：待补充')).toBeVisible()
  expect(within(table).getByText('筛选：状态为可使用')).toBeVisible()
  expect(within(table).getByText('字段 登录结果')).toBeVisible()
})

it('shows row-level conflict and unknown details without presenting them as confirmed or empty', () => {
  render(<TaskDataWrites writes={[
    { kind: 'recordUpdated', tableDisplay: '邮箱表', recordDisplay: 'mail-001', beforeSummary: '备注：旧值', afterSummary: '备注：新值', detail: '记录已被人工修改，请重新读取', outcome: 'conflict' },
    { kind: 'fieldModified', tableDisplay: '账号表', recordDisplay: '备注', referenceDisplay: '字段 备注', detail: '请求已提交，正在核对最终结果', outcome: 'unknown' },
  ]} />)

  expect(screen.getByText('记录已被人工修改，请重新读取')).toBeVisible()
  expect(screen.getByText('请求已提交，正在核对最终结果')).toBeVisible()
  expect(screen.getByText('写入冲突')).toHaveAttribute('data-table-status', 'danger')
  expect(screen.getByText('结果待核对')).toHaveAttribute('data-table-status', 'warning')
  expect(screen.queryByText('已确认')).not.toBeInTheDocument()
  expect(screen.queryByText('本任务没有项目数据操作')).not.toBeInTheDocument()
})

it('degrades an unknown operation kind into readable evidence', () => {
  render(<TaskDataWrites writes={[
    { kind: 'futureCapability', tableDisplay: '账号表', recordDisplay: '目标对象', detail: '服务返回的操作摘要', outcome: 'succeeded' },
  ]} />)

  expect(screen.getByText('数据操作')).toBeVisible()
  expect(screen.getByText('服务返回的操作摘要')).toBeVisible()
  expect(screen.getByText('已确认')).toBeVisible()
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
  expect(screen.getByRole('table', { name: '项目数据操作结果' })).toHaveAttribute('aria-busy', 'true')
  expect(screen.getByRole('status')).toHaveTextContent('正在读取项目数据操作')
  expect(screen.queryByText('本任务没有项目数据操作')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites />)
  expect(screen.getByText('项目数据操作尚未读取')).toBeVisible()
  expect(screen.queryByText('本任务没有项目数据操作')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites error="服务暂时不可用" />)
  expect(screen.getByRole('alert')).toHaveTextContent('项目数据操作读取失败：服务暂时不可用')
  expect(screen.queryByText('本任务没有项目数据操作')).not.toBeInTheDocument()

  view.rerender(<TaskDataWrites writes={[]} />)
  expect(screen.getByText('本任务没有项目数据操作')).toBeVisible()
})

it('preserves confirmed rows while a refresh fails and never exposes internal identities', () => {
  render(<TaskDataWrites writes={[
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: '张三的账号', referenceDisplay: '账号记录 #1008', outcome: 'succeeded' },
  ]} error="写入事实刷新失败" />)

  expect(screen.getByText('账号记录 #1008')).toBeVisible()
  expect(screen.getByRole('alert')).toBeVisible()
  expect(screen.queryByText(/lease/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/revision/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/[0-9a-f]{8}-[0-9a-f-]{27,}/i)).not.toBeInTheDocument()
  expect(screen.queryByText('本任务没有项目数据操作')).not.toBeInTheDocument()
})

it('compacts UUID-backed references into readable record labels', () => {
  const uuid = 'e97b544d-3b57-424d-ad2f-f166e6119027'
  render(<TaskDataWrites writes={[
    { kind: 'recordCreated', tableDisplay: '账号表', recordDisplay: `uuid · ${uuid}`, referenceDisplay: `uuid · ${uuid}`, outcome: 'succeeded' },
  ]} />)

  expect(screen.getAllByText('记录 · e97b544d…9027')).toHaveLength(2)
  expect(screen.queryByText(uuid, { exact: false })).not.toBeInTheDocument()
})

it('uses the shared scrollable fine-grid table and wraps long values', () => {
  const tableDisplay = '跨区域账号归档数据表'.repeat(20)
  const recordDisplay = '张三的企业级账号及长期业务说明'.repeat(25)
  const referenceDisplay = '账号记录｜企业客户｜2026-09'.repeat(20)
  render(<TaskDataWrites writes={[{ kind: 'recordCreated', tableDisplay, recordDisplay, referenceDisplay, outcome: 'succeeded' }]} />)

  expect(screen.getByRole('region', { name: '项目数据操作表格' })).toHaveClass('af-table-scroll', 'overflow-auto', 'rounded-control')
  expect(screen.getByRole('table', { name: '项目数据操作结果' })).toHaveClass('af-table')
  expect(screen.getByText(tableDisplay)).toHaveClass('break-words')
  expect(screen.getByText(recordDisplay)).toHaveClass('break-words')
  expect(screen.getByText(referenceDisplay)).toHaveClass('break-words')
})
