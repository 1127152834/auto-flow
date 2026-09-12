import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ProjectPage, ProjectSummary } from '../types'
import { ProjectDirectory } from './ProjectDirectory'

const summary = { projectId: 'p1', name: '客户采集', description: '华东客户', lifecycleState: 'active', updatedAt: '2026-09-13T10:00:00Z', lastOpenedAt: null } as ProjectSummary
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

it('opens from the row and keeps edit as a separate action', async () => {
  const onOpen = vi.fn(); const onEdit = vi.fn(); const user = userEvent.setup()
  render(<ProjectDirectory page={page([summary])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled={false} error={null} onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={onOpen} onEdit={onEdit} />)
  fireEvent.click(screen.getByRole('row', { name: /客户采集/ }))
  expect(onOpen).toHaveBeenCalledWith(summary)
  await user.click(screen.getByRole('button', { name: '编辑客户采集' }))
  expect(onEdit).toHaveBeenCalledWith(summary)
  expect(onOpen).toHaveBeenCalledTimes(1)
  screen.getByRole('button', { name: '编辑客户采集' }).focus()
  await user.keyboard('{Enter}')
  expect(onEdit).toHaveBeenCalledTimes(2)
  expect(onOpen).toHaveBeenCalledTimes(1)
  expect(screen.queryByText(/运行次数|自动化数量/)).not.toBeInTheDocument()
})

it('keeps stale rows visible and reports a refresh failure', () => {
  render(<ProjectDirectory page={page([summary])} conditions={{ query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }} loading={false} refreshing={false} disabled error="刷新项目失败" onConditionsChange={vi.fn()} onRefresh={vi.fn()} onCreate={vi.fn()} onOpen={vi.fn()} onEdit={vi.fn()} />)
  expect(screen.getByText('客户采集')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('刷新项目失败')
  expect(screen.getByRole('button', { name: '新建项目' })).toBeDisabled()
})
