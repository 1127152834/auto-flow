import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import type { Automation, AutomationValidation } from '../types'
import { AutomationDirectory } from './AutomationDirectory'

choiceTestEnvironment()
afterEach(cleanup)

const automation = (id: string, name: string, inputs = 1): Automation => ({
  automationId: id, projectId: 'project-1', workflowId: `workflow-${id}`, name, description: `${name}的用途说明`, managementRevision: 2,
  inputPlan: { inputs: Array.from({ length: inputs }, (_, index) => ({ inputId: `input-${index}`, alias: `输入${index}`, tableId: 'table-1', datasetGeneration: 'generation-1', mode: 'independent', required: false, fieldBindings: [], filter: { type: 'and', children: [] }, orderBy: [] })) },
  parameterSchema: [], environmentPolicy: { source: 'newFromProfile' },
  runPolicy: { maxTasks: 10, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 3600 },
  createdAt: '2026-09-10T01:00:00Z', updatedAt: '2026-09-10T02:00:00Z',
})
const items = [automation('a', '资料整理'), automation('b', '链接采集', 0)]
const ready: AutomationValidation = { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '2026-09-10T02:01:00Z' }
const props = () => ({ items, total: 2, page: 1, pageSize: 20, query: '', sort: 'updatedAt' as const, onQueryChange: vi.fn(), onSortChange: vi.fn(), onPageChange: vi.fn(), onCreate: vi.fn(), onOpen: vi.fn(), onEdit: vi.fn(), onRetry: vi.fn() })

it('opens the project Studio before the first automation exists and respects lifecycle restrictions', async () => {
  const p = props(), user = userEvent.setup(), onOpenStudio = vi.fn()
  const view = render(<AutomationDirectory {...p} items={[]} total={0} onOpenStudio={onOpenStudio} />)
  await user.click(screen.getByRole('button', { name: '工作流工作台' }))
  expect(onOpenStudio).toHaveBeenCalledTimes(1)
  expect(p.onCreate).not.toHaveBeenCalled()
  view.rerender(<AutomationDirectory {...p} items={[]} total={0} refreshing onOpenStudio={onOpenStudio} />)
  expect(screen.getByRole('button', { name: '工作流工作台' })).toBeDisabled()
  view.rerender(<AutomationDirectory {...p} items={[]} total={0} readOnly onOpenStudio={onOpenStudio} />)
  expect(screen.queryByRole('button', { name: '工作流工作台' })).toBeNull()
})

it('renders gallery cards from real automation facts without inventing validation', () => {
  render(<AutomationDirectory {...props()} validationById={{ a: ready }} />)
  expect(screen.getByRole('heading', { name: '自动化 2 个' })).toBeVisible()
  const cards = screen.getAllByRole('article')
  expect(cards).toHaveLength(2)
  expect(within(cards[0]).getByText('1 项数据输入')).toBeVisible()
  expect(within(cards[1]).getByText('无数据输入')).toBeVisible()
  expect(within(cards[0]).getByText('配置已保存')).toBeVisible()
  expect(within(cards[0]).getByText('可以运行')).toBeVisible()
  expect(within(cards[1]).queryByText('可以运行')).toBeNull()
  expect(screen.getAllByTestId('automation-document-icon')).toHaveLength(2)
})

it('keeps open and more actions independent', async () => {
  const p = props(), user = userEvent.setup()
  render(<AutomationDirectory {...p} />)
  await user.click(screen.getByRole('button', { name: '打开自动化 资料整理' }))
  expect(p.onOpen).toHaveBeenCalledWith(items[0])
  expect(p.onEdit).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '更多资料整理操作' }))
  await user.click(screen.getByRole('menuitem', { name: '编辑基本信息' }))
  expect(p.onEdit).toHaveBeenCalledWith(items[0])
  expect(p.onOpen).toHaveBeenCalledTimes(1)
  expect(document.querySelector('button button')).toBeNull()
  expect(screen.queryByText('删除自动化')).toBeNull()
})

it('offers deletion from the card menu only where the host can delete', async () => {
  const p = props(), user = userEvent.setup()
  const onDelete = vi.fn()
  const view = render(<AutomationDirectory {...p} onDelete={onDelete} />)
  await user.click(screen.getByRole('button', { name: '更多资料整理操作' }))
  await user.click(screen.getByRole('menuitem', { name: '删除自动化' }))
  expect(onDelete).toHaveBeenCalledWith(items[0])
  expect(p.onOpen).not.toHaveBeenCalled()
  view.rerender(<AutomationDirectory {...p} readOnly />)
  expect(screen.queryByText('删除自动化')).toBeNull()
})

it('emits controlled search, clear, all four backend sorts and page changes', async () => {
  const p = props(), user = userEvent.setup()
  const view = render(<AutomationDirectory {...p} total={45} />)
  fireEvent.change(screen.getByRole('searchbox', { name: '搜索自动化' }), { target: { value: '资料' } })
  expect(p.onQueryChange).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '应用自动化搜索' }))
  expect(p.onQueryChange).toHaveBeenCalledWith('资料')
  view.rerender(<AutomationDirectory {...p} query="资料" total={45} />)
  await user.click(screen.getByRole('button', { name: '清除搜索' }))
  expect(p.onQueryChange).toHaveBeenLastCalledWith('')
  for (const value of ['name', '-name', 'updatedAt', '-updatedAt']) {
    view.rerender(<AutomationDirectory {...p} query="资料" total={45} sort={value === 'updatedAt' ? 'name' : 'updatedAt'} />)
    await chooseOption(user, screen.getByRole('combobox', { name: '自动化排序' }), value)
    expect(p.onSortChange).toHaveBeenLastCalledWith(value)
  }
  await user.click(screen.getByRole('button', { name: '下一页' }))
  expect(p.onPageChange).toHaveBeenCalledWith(2)
})

it('distinguishes empty, no results, loading and initial error', () => {
  const p = props(), view = render(<AutomationDirectory {...p} items={[]} total={0} />)
  expect(screen.getByRole('heading', { name: '还没有自动化' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '新建自动化' }))
  expect(p.onCreate).toHaveBeenCalled()
  view.rerender(<AutomationDirectory {...p} items={[]} total={0} query="周报" />)
  expect(screen.getByRole('heading', { name: '没有找到匹配的自动化' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '清除搜索条件' }))
  expect(p.onQueryChange).toHaveBeenCalledWith('')
  view.rerender(<AutomationDirectory {...p} items={[]} total={0} loading />)
  expect(screen.getByRole('status')).toHaveTextContent('正在加载自动化')
  expect(screen.getAllByTestId('automation-skeleton')).toHaveLength(6)
  view.rerender(<AutomationDirectory {...p} items={[]} total={0} errorMessage="服务不可用" />)
  expect(screen.getByRole('alert')).toHaveTextContent('自动化暂时无法加载')
  fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
  expect(p.onRetry).toHaveBeenCalled()
})

it('preserves stale cards on refresh failure and exposes warning retry', () => {
  const p = props()
  render(<AutomationDirectory {...p} errorMessage="刷新失败" refreshing />)
  expect(screen.getByText('资料整理')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('刷新失败')
  fireEvent.click(screen.getByRole('button', { name: '重试读取' }))
  expect(p.onRetry).toHaveBeenCalled()
})

it('allows opening archived project cards but removes all create and edit actions', async () => {
  const p = props(), user = userEvent.setup()
  render(<AutomationDirectory {...p} readOnly />)
  expect(screen.queryByRole('button', { name: '新建自动化' })).toBeNull()
  expect(screen.queryByRole('button', { name: '更多资料整理操作' })).toBeNull()
  await user.click(screen.getByRole('button', { name: '查看自动化 资料整理' }))
  expect(p.onOpen).toHaveBeenCalledWith(items[0])
  expect(p.onEdit).not.toHaveBeenCalled()
})

it('uses a responsive two-column grid and contains long unbroken text', () => {
  render(<AutomationDirectory {...props()} items={[automation('long', 'A'.repeat(180))]} total={1} />)
  const grid = screen.getByTestId('automation-grid')
  expect(grid).toHaveClass('grid-cols-1', 'lg:grid-cols-2')
  expect(screen.getByRole('heading', { name: 'A'.repeat(180) })).toHaveClass('[overflow-wrap:anywhere]')
})
