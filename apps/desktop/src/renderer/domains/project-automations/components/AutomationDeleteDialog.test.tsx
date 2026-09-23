import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import type { components } from '../../../shared/api/generated'
import type { Automation, AutomationImpact } from '../types'
import { AutomationDeleteDialog } from './AutomationDeleteDialog'

type Operation = components['schemas']['ProjectOperationView']

afterEach(cleanup)

const automation = { automationId: 'a1', name: '内容采集', managementRevision: 7 } as Automation
const resource = { type: 'automation', projectId: 'p1', automationId: 'a1' } as AutomationImpact['impacts'][number]['resource']
const impact = {
  impactRevision: 12,
  impacts: [
    { code: 'AUTOMATION_CONFIGURATION', resource, message: '自动化名称、说明与草稿配置', blocking: false },
    { code: 'RUN_PLANS', resource, message: '运行方案 3 个及其任务与事件', blocking: false },
    { code: 'REFERENCED_RESOURCES_KEPT', resource, message: '数据表与记录、外部来源、其它自动化与项目资源保留', blocking: false },
    { code: 'WORKFLOW_DOCUMENT_KEPT', resource, message: '关联的工作流文档保留，只解除关联', blocking: false },
  ],
  blockers: [
    { code: 'AUTOMATION_BUSY', resource, state: 'running', message: '批次尚未结束，先停止或等它收尾' },
    { code: 'MANUAL_PENDING', resource: { type: 'task', projectId: 'p1', taskId: 't1' }, state: 'resume_requested', message: '人工事项尚未结束，请先完成或取消处理' },
  ],
} as AutomationImpact

const open = (override: Partial<Parameters<typeof AutomationDeleteDialog>[0]> = {}) => render(
  <AutomationDeleteDialog open automation={automation} onOpenChange={vi.fn()} onLoadImpact={vi.fn().mockResolvedValue(impact)} onSubmit={vi.fn()} {...override} />,
)

it('splits the real impact into what is deleted and what is kept, and lists the blockers', async () => {
  open()
  const deleted = within(await screen.findByRole('region', { name: '将删除' }))
  expect(deleted.getByText('自动化名称、说明与草稿配置')).toBeVisible()
  expect(deleted.getByText('运行方案 3 个及其任务与事件')).toBeVisible()
  expect(deleted.queryByText('关联的工作流文档保留，只解除关联')).toBeNull()
  const kept = within(screen.getByRole('region', { name: '将保留' }))
  expect(kept.getByText('关联的工作流文档保留，只解除关联')).toBeVisible()
  expect(kept.getByText('数据表与记录、外部来源、其它自动化与项目资源保留')).toBeVisible()
  expect(screen.getByText('批次尚未结束，先停止或等它收尾（running）')).toBeVisible()
  expect(screen.getByText('人工事项尚未结束，请先完成或取消处理（resume_requested）')).toBeVisible()
})

it('requires the exact automation name and submits the frozen impact revision with an unlink disposition', async () => {
  const user = userEvent.setup()
  const submit = vi.fn().mockResolvedValue({ operationId: 'o1', status: 'succeeded', kind: 'deleteAutomation' } as Operation)
  open({ onSubmit: submit })
  const confirm = await screen.findByRole('button', { name: '删除自动化' })
  expect(confirm).toBeDisabled()
  await user.type(screen.getByLabelText('确认自动化名称'), '内容采')
  expect(confirm).toBeDisabled()
  await user.type(screen.getByLabelText('确认自动化名称'), '集')
  expect(confirm).toBeEnabled()
  await user.click(confirm)
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ impactRevision: 12, expectedManagementRevision: 7, workflowDisposition: 'unlink' }))
})

it('drops the confirmation and asks for a fresh impact check when the impact is stale', async () => {
  const user = userEvent.setup()
  const load = vi.fn().mockResolvedValue(impact)
  const submit = vi.fn().mockRejectedValue(new ApiClientError('影响范围已变化', 412, 'PRECONDITION_FAILED'))
  open({ onLoadImpact: load, onSubmit: submit })
  await user.type(await screen.findByLabelText('确认自动化名称'), automation.name)
  await user.click(screen.getByRole('button', { name: '删除自动化' }))
  expect(await screen.findByText('影响范围可能已变化，请重新核对后再确认。')).toBeVisible()
  expect(screen.getByLabelText('确认自动化名称')).toHaveValue('')
  await user.click(screen.getByRole('button', { name: '重新核对影响' }))
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
})

it.each([
  ['running' as const, '删除命令已接受，正在处理。'],
  ['succeeded' as const, '自动化已删除。'],
])('reports an accepted command separately from a finished one (%s)', async (status, expected) => {
  const user = userEvent.setup()
  open({ onSubmit: vi.fn().mockResolvedValue({ operationId: 'o2', status, kind: 'deleteAutomation' } as Operation) })
  await user.type(await screen.findByLabelText('确认自动化名称'), automation.name)
  await user.click(screen.getByRole('button', { name: '删除自动化' }))
  expect(await screen.findByText(expected)).toBeVisible()
})

it('keeps the command disabled while the host blocks editing', async () => {
  const user = userEvent.setup()
  open({ disabled: true })
  expect(await screen.findByRole('button', { name: '删除自动化' })).toBeDisabled()
  await user.type(screen.getByLabelText('确认自动化名称'), automation.name)
  expect(screen.getByRole('button', { name: '删除自动化' })).toBeDisabled()
})
