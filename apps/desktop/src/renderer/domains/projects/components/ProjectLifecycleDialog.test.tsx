import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import type { ProjectLifecycleImpact, ProjectOperationPage, ProjectOperationView, ProjectView } from '../types'
import { reportedCleanupResidue } from '../cleanup-residue'
import { ProjectLifecycleDialog } from './ProjectLifecycleDialog'

const project = { projectId: 'p1', name: '内容采集项目', description: '', managementRevision: 4 } as ProjectView

const impact = {
  impactRevision: 9,
  unsyncedCount: 2,
  blockers: [{ code: 'BATCH_ACTIVE', resource: { type: 'batch', projectId: 'p1', batchId: 'b1' }, state: 'running', message: '批次尚未结束，先停止或等它收尾' }],
  impacts: [{ code: 'PROJECT_TABLES', resource: { type: 'project', projectId: 'p1' }, message: '删除 2 张数据表及其记录', blocking: false }],
} as unknown as ProjectLifecycleImpact

const operation = { operationId: 'o1', status: 'running', kind: 'deleteProject' } as unknown as ProjectOperationView
afterEach(cleanup)

it('lists the real impact, the blockers and the unsynced changes before deleting', async () => {
  render(<ProjectLifecycleDialog open action="delete" project={project} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue(impact)} onSubmit={vi.fn()} />)
  expect(await screen.findByText('删除 2 张数据表及其记录')).toBeVisible()
  expect(screen.getByText('批次尚未结束，先停止或等它收尾（running）')).toBeVisible()
  expect(screen.getByText('未推送变化 2 条：删除后不会补发。')).toBeVisible()
  expect(screen.getByRole('button', { name: '永久删除' })).toBeDisabled()
})

it('requires the exact project name and refuses a blocked delete', async () => {
  const user = userEvent.setup()
  const blocked = { ...impact, blockers: [] } as ProjectLifecycleImpact
  render(<ProjectLifecycleDialog open action="delete" project={project} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue(blocked)} onSubmit={vi.fn()} />)
  const confirm = await screen.findByRole('button', { name: '永久删除' })
  expect(confirm).toBeDisabled()
  await user.type(screen.getByLabelText('确认项目名称'), '内容采集')
  expect(confirm).toBeDisabled()
  await user.type(screen.getByLabelText('确认项目名称'), '项目')
  expect(confirm).toBeEnabled()
})

it('drops the confirmation and asks for a fresh impact check on a stale revision', async () => {
  const user = userEvent.setup()
  const load = vi.fn().mockResolvedValue({ ...impact, blockers: [] })
  const submit = vi.fn().mockRejectedValue(new ApiClientError('影响范围已变化', 412, 'PRECONDITION_FAILED'))
  render(<ProjectLifecycleDialog open action="delete" project={project} onOpenChange={vi.fn()} onLoadImpact={load} onSubmit={submit} />)
  await user.type(await screen.findByLabelText('确认项目名称'), project.name)
  await user.click(screen.getByRole('button', { name: '永久删除' }))
  expect(await screen.findByText('影响范围可能已变化，请重新核对后再确认。')).toBeVisible()
  expect(screen.getByLabelText('确认项目名称')).toHaveValue('')
  await user.click(screen.getByRole('button', { name: '重新核对影响' }))
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
})

it('reports cleanup residue instead of claiming the project is gone', async () => {
  const failed = { ...operation, status: 'failed', error: { code: 'DELETE_CLEANUP_FAILED', details: { cleanup: { residue: ['/tmp/environments/instances/e1'] } } } } as unknown as ProjectOperationView
  render(<ProjectLifecycleDialog open action="delete" project={project} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue({ ...impact, blockers: [] })} onSubmit={vi.fn().mockResolvedValue(failed)} />)
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('确认项目名称'), project.name)
  await user.click(screen.getByRole('button', { name: '永久删除' }))
  expect(await screen.findByText('本地文件未能完全清理')).toBeVisible()
  expect(screen.getByText('/tmp/environments/instances/e1')).toBeVisible()
  expect(screen.getByRole('button', { name: '永久删除' })).toBeDisabled()
})

it('archives with the confirmed impact and revision', async () => {
  const user = userEvent.setup()
  const submit = vi.fn().mockResolvedValue({ ...operation, status: 'succeeded', kind: 'archiveProject' })
  render(<ProjectLifecycleDialog open action="archive" project={project} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue({ ...impact, blockers: [] })} onSubmit={submit} />)
  await user.click(await screen.findByRole('button', { name: '归档项目' }))
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ impactRevision: 9, expectedManagementRevision: 4, confirmationName: '' }))
  expect(await screen.findByText('归档命令已接受，正在收尾。')).toBeVisible()
})

it('retries the cleanup of a project that is still deleting', async () => {
  const user = userEvent.setup()
  const stuck = { ...project, lifecycleState: 'deleting' } as unknown as ProjectView
  const residuePage = { items: [{ ...operation, status: 'failed', kind: 'deleteProject', error: { code: 'DELETE_CLEANUP_FAILED', details: { cleanup: { residue: ['/tmp/environments/instances/e1'] } } } }] } as unknown as ProjectOperationPage
  const submit = vi.fn().mockResolvedValue({ ...operation, status: 'running' })
  render(<ProjectLifecycleDialog open action="delete" project={stuck} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue({ ...impact, blockers: [] })} onLoadResidue={() => Promise.resolve(reportedCleanupResidue(residuePage))} onSubmit={submit} />)

  expect(await screen.findByText('/tmp/environments/instances/e1')).toBeVisible()
  expect(screen.getAllByText(/上次本地文件清理未完成/).length).toBeGreaterThan(0)
  expect(screen.getByText('这是服务已经确认的残留清单，重试只处理这些文件。')).toBeVisible()
  const confirm = screen.getByRole('button', { name: '重试清理' })
  expect(confirm).toBeDisabled()

  await user.type(screen.getByLabelText('确认项目名称'), project.name)
  expect(confirm).toBeEnabled()
  await user.click(confirm)
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ impactRevision: 9, expectedManagementRevision: 4, confirmationName: project.name }))
  expect(await screen.findByText('命令已接受，正在处理。')).toBeVisible()
})
