import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { EnvironmentDirectory } from './EnvironmentDirectory'

afterEach(cleanup)

const environment = {
  ref: { projectId: 'p', environmentId: '11111111-1111-4111-8111-111111111111', contentGeneration: 2, metadataRevision: 1 },
  name: '登录环境',
  notes: '主账号',
  state: 'ready' as const,
  profileId: 'profile',
  unavailableReason: null,
  createdAt: '2026-09-17T00:00:00Z',
  updatedAt: '2026-09-17T00:00:00Z',
  createdFromSource: 'newFromProfile',
  createdFromTaskId: '22222222-2222-4222-8222-222222222222',
  linkedRecordCount: 3,
}

it('lists persistent environments and keeps empty and error states distinct', () => {
  const onOpen = vi.fn()
  render(<EnvironmentDirectory page={{ items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }} onOpen={onOpen} onRetry={vi.fn()} />)
  expect(screen.getByText('还没有持久环境')).toBeVisible()
  cleanup()
  render(<EnvironmentDirectory page={{ items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }} query="xyz" onOpen={onOpen} onRetry={vi.fn()} />)
  expect(screen.getByText('没有匹配的持久环境')).toBeVisible()
  cleanup()
  render(<EnvironmentDirectory error="读取失败" onOpen={onOpen} onRetry={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('持久环境读取失败：读取失败')
  expect(screen.queryByText('还没有持久环境')).not.toBeInTheDocument()
})

it('renders the directory columns the artboard asks for and keeps internals out of them', async () => {
  const user = userEvent.setup()
  const onOpen = vi.fn()
  const onOpenTask = vi.fn()
  const onMaintenance = vi.fn()
  render(<EnvironmentDirectory
    page={{ items: [environment], page: 1, pageSize: 50, total: 1, sort: '-updatedAt' }}
    onOpen={onOpen}
    onOpenTask={onOpenTask}
    onMaintenance={onMaintenance}
    onRetry={vi.fn()}
  />)
  for (const column of ['环境', '状态', '最近来源', '保存时间', '引用', '更多']) expect(screen.getByRole('columnheader', { name: column })).toBeVisible()
  expect(screen.getByText('登录环境')).toBeVisible()
  expect(screen.getByText('按浏览器配置新建')).toBeVisible()
  expect(screen.getByText('就绪')).toBeVisible()
  // 引用 是本环境的记录关联数，不是内部代次
  expect(screen.getByRole('row', { name: /登录环境/ })).toHaveTextContent('3')
  // 内部内容代次不再作为目录列暴露给用户
  expect(screen.queryByRole('columnheader', { name: '内容代次' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: `更多 ${environment.name} 操作` }))
  await user.click(await screen.findByRole('menuitem', { name: '查看环境' }))
  expect(onOpen).toHaveBeenCalledWith('11111111-1111-4111-8111-111111111111')
  await user.click(screen.getByRole('button', { name: `更多 ${environment.name} 操作` }))
  await user.click(await screen.findByRole('menuitem', { name: '维护打开' }))
  expect(onMaintenance).toHaveBeenCalledWith({ environmentId: '11111111-1111-4111-8111-111111111111', contentGeneration: 2 })
  await user.click(screen.getByRole('button', { name: '查看任务' }))
  expect(onOpenTask).toHaveBeenCalledWith('22222222-2222-4222-8222-222222222222')
})
