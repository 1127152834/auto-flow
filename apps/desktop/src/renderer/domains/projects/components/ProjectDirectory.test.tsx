import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ProjectPage, ProjectSummary } from '../types'
import { ProjectDirectory } from './ProjectDirectory'

const summary = { projectId: 'p1', name: '客户采集', description: '华东客户', lifecycleState: 'active', updatedAt: '2026-09-13T10:00:00Z', lastOpenedAt: '2026-09-13T09:00:00Z' } as ProjectSummary
const page = (items: ProjectSummary[], total = items.length) => ({ items, total, page: 1, pageSize: 50, sort: '-lastOpenedAt' }) as ProjectPage
class ResizeObserverStub { observe() {}; unobserve() {}; disconnect() {} }
beforeEach(() => vi.stubGlobal('ResizeObserver', ResizeObserverStub))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('distinguishes an empty directory from no matching results', () => {
  const props = { conditions: { query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 } as const, loading: false, refreshing: false, disabled: false, error: null, onConditionsChange: vi.fn(), onRefresh: vi.fn(), onCreate: vi.fn(), onOpen: vi.fn(), onEdit: vi.fn() }
  const view = render(<ProjectDirectory {...props} page={page([])} />)
  expect(screen.getByText('还没有项目')).toBeVisible()
  view.rerender(<ProjectDirectory {...props} conditions={{ ...props.conditions, query: '缺失' }} page={page([])} />)
  expect(screen.getByText('没有匹配的项目')).toBeVisible()
})

it('opens from the compact card and keeps edit as a separate action', async () => {
  const onOpen = vi.fn(); const onEdit = vi.fn(); const user = userEvent.setup()
  render(<ProjectDirectory page={page([summary])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={onOpen} onEdit={onEdit} />)
  fireEvent.click(screen.getByRole('article'))
  expect(onOpen).toHaveBeenCalledWith(summary)
  await user.click(screen.getByRole('button', { name: '更多客户采集操作' }))
  await user.click(screen.getByRole('menuitem', { name: '编辑项目' }))
  expect(onEdit).toHaveBeenCalledWith(summary)
  expect(onOpen).toHaveBeenCalledTimes(1)
  screen.getByRole('button', { name: '客户采集' }).focus()
  await user.keyboard('{Enter}')
  expect(onOpen).toHaveBeenCalledTimes(2)
  expect(screen.queryByText(/运行次数|自动化数量/)).not.toBeInTheDocument()
})

it('shows at most six visited active projects in recent mode', () => {
  const visited = Array.from({ length: 7 }, (_, index) => ({ ...summary, projectId: `p${index}`, name: `项目${index}` }))
  const unvisited = { ...summary, projectId: 'never', name: '从未访问', lastOpenedAt: null }
  const archived = { ...summary, projectId: 'archived', name: '归档项目', lifecycleState: 'archived' } as ProjectSummary
  render(<ProjectDirectory mode="recent" recentItems={[...visited, unvisited, archived]} page={page([])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} recentLoading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getAllByRole('article')).toHaveLength(6)
  expect(screen.queryByText('从未访问')).not.toBeInTheDocument()
  expect(screen.queryByText('归档项目')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '查看全部项目' })).toBeVisible()
  expect(screen.queryByRole('row')).not.toBeInTheDocument()
})

it('keeps recent search visually empty and avoids duplicate empty-state actions', () => {
  render(<ProjectDirectory mode="recent" recentItems={[]} page={page([])} conditions={{ query: '全部目录条件', lifecycle: 'active', sort: '-lastOpenedAt', page: 2, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByRole('searchbox', { name: '搜索项目' })).toHaveValue('')
  expect(screen.getAllByRole('button', { name: '查看全部项目' })).toHaveLength(1)
  expect(screen.getAllByRole('button', { name: '新建项目' })).toHaveLength(1)
})

it('does not claim stale content exists when a recent load fails empty', () => {
  render(<ProjectDirectory mode="recent" recentItems={[]} recentError="刷新项目失败" page={page([])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('刷新项目失败')
  expect(screen.getByRole('alert')).not.toHaveTextContent('仍显示上次')
})

it('switches recent search to all while applying the query', async () => {
  const onModeChange = vi.fn(); const onConditionsChange = vi.fn()
  render(<ProjectDirectory mode="recent" recentItems={[summary]} page={page([])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 3, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onModeChange={onModeChange} onConditionsChange={onConditionsChange} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  fireEvent.change(screen.getByRole('searchbox', { name: '搜索项目' }), { target: { value: '采集' } })
  expect(onModeChange).toHaveBeenCalledWith('all')
  expect(onConditionsChange).toHaveBeenCalledWith(expect.objectContaining({ query: '采集', page: 1 }))
})

it('opens a project card without letting its edit menu trigger open', async () => {
  const onOpen = vi.fn(); const onEdit = vi.fn(); const user = userEvent.setup()
  render(<ProjectDirectory mode="recent" recentItems={[summary]} page={page([])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={onOpen} onEdit={onEdit} />)
  await user.click(screen.getByRole('article'))
  expect(onOpen).toHaveBeenCalledWith(summary)
  await user.click(screen.getByRole('button', { name: '更多客户采集操作' }))
  await user.click(screen.getByRole('menuitem', { name: '编辑项目' }))
  expect(onEdit).toHaveBeenCalledWith(summary)
  expect(onOpen).toHaveBeenCalledTimes(1)
})

it('allows an unbroken project name to wrap inside the open button', () => {
  const longName = '甲'.repeat(36)
  render(<ProjectDirectory mode="recent" recentItems={[{ ...summary, name: longName }]} page={page([])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByRole('button', { name: longName })).toHaveClass('break-all', 'whitespace-normal')
})

it('keeps stale rows visible and reports a refresh failure', () => {
  render(<ProjectDirectory page={page([summary])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled error="刷新项目失败" onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByText('客户采集')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('刷新项目失败')
  expect(screen.getByRole('button', { name: '新建项目' })).toBeDisabled()
})
