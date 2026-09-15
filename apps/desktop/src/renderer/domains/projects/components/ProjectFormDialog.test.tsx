import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import type { ProjectView } from '../types'
import { ProjectFormDialog } from './ProjectFormDialog'

const project = { projectId: 'p1', name: '原项目', description: '原说明', managementRevision: 2 } as ProjectView
afterEach(cleanup)

it('focuses the name when its Unicode code-point limit is exceeded', async () => {
  const user = userEvent.setup()
  render(<ProjectFormDialog open project={null} draftSession="create-1" onOpenChange={vi.fn()} onSubmit={vi.fn()} />)
  await user.type(screen.getByLabelText('项目名称'), '😀'.repeat(37))
  await user.click(screen.getByRole('button', { name: '创建项目' }))
  expect(await screen.findByText('项目名称最多 36 个字符')).toBeVisible()
  expect(screen.getByLabelText('项目名称')).toHaveFocus()
})

it('does not overwrite a dirty draft when refreshed project data arrives', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  const view = render(<ProjectFormDialog open project={project} draftSession="edit-1" onOpenChange={vi.fn()} onSubmit={onSubmit} />)
  const input = screen.getByLabelText('项目名称')
  await user.clear(input)
  await user.type(input, '我的草稿')
  view.rerender(<ProjectFormDialog open project={{ ...project, name: '服务端新名称', managementRevision: 3 } as ProjectView} draftSession="edit-1" onOpenChange={vi.fn()} onSubmit={onSubmit} />)
  expect(input).toHaveValue('我的草稿')
  await user.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: '我的草稿' }), 2))
})

it('keeps the draft on conflict and offers the latest server content', async () => {
  const user = userEvent.setup()
  const latest = { ...project, name: '另一处修改', managementRevision: 3 } as ProjectView
  render(<ProjectFormDialog open project={project} draftSession="edit-1" onOpenChange={vi.fn()} onSubmit={vi.fn().mockRejectedValue(new ApiClientError('项目已变化', 409, 'REVISION_CONFLICT'))} onLoadLatest={vi.fn().mockResolvedValue(latest)} />)
  await user.clear(screen.getByLabelText('项目名称'))
  await user.type(screen.getByLabelText('项目名称'), '我的草稿')
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('另一处修改')
  expect(screen.getByLabelText('项目名称')).toHaveValue('我的草稿')
  await user.click(screen.getByRole('button', { name: '基于最新内容重新编辑' }))
  expect(screen.getByLabelText('项目名称')).toHaveValue('另一处修改')
})

it('submits once and cannot close while saving', async () => {
  let finish!: () => void
  const pending = new Promise<void>(resolve => { finish = resolve })
  const onSubmit = vi.fn(() => pending)
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  render(<ProjectFormDialog open project={project} draftSession="edit-1" onOpenChange={onOpenChange} onSubmit={onSubmit} />)
  await user.dblClick(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  await user.keyboard('{Escape}')
  expect(onOpenChange).not.toHaveBeenCalled()
  finish()
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
})

it('locks synchronous Enter, submit, and click triggers to one request', async () => {
  const pending = deferred<void>()
  const onSubmit = vi.fn(() => pending.promise)
  render(<ProjectFormDialog open project={project} draftSession="edit-lock" onOpenChange={vi.fn()} onSubmit={onSubmit} />)
  const form = document.querySelector<HTMLFormElement>('#project-form')!
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  screen.getByRole('button', { name: '保存' }).click()
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  pending.resolve()
})

it('captures the session ticket before asynchronous validation completes', async () => {
  const onSubmit = vi.fn()
  const view = render(<ProjectFormDialog open project={project} draftSession="old" submissionEpoch="i1:old" onOpenChange={vi.fn()} onSubmit={onSubmit} />)
  fireEvent.submit(document.querySelector<HTMLFormElement>('#project-form')!)
  view.rerender(<ProjectFormDialog open project={project} draftSession="new" submissionEpoch="i1:new" onOpenChange={vi.fn()} onSubmit={onSubmit} />)
  await Promise.resolve(); await Promise.resolve()
  expect(onSubmit).not.toHaveBeenCalled()
})

it('makes fields readonly synchronously for an in-flight submit', async () => {
  const pending = deferred<void>()
  render(<ProjectFormDialog open project={project} draftSession="saving" onOpenChange={vi.fn()} onSubmit={() => pending.promise} />)
  fireEvent.submit(document.querySelector<HTMLFormElement>('#project-form')!)
  await waitFor(() => expect(screen.getByLabelText('项目名称')).toHaveAttribute('readonly'))
  expect(screen.getByLabelText('项目描述')).toHaveAttribute('readonly')
  pending.resolve()
})

it('maps non-revision 409 by code without echoing diagnostics or loading a newer project', async () => {
  const loadLatest = vi.fn()
  const user = userEvent.setup()
  render(<ProjectFormDialog open project={project} draftSession="lifecycle" onOpenChange={vi.fn()} onSubmit={vi.fn().mockRejectedValue(new ApiClientError('项目正在删除 ab806c63-6b08-460b-bd2a-f3f6d2b07116', 409, 'LIFECYCLE_CONFLICT'))} onLoadLatest={loadLatest} />)
  await user.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('项目当前为只读状态')
  expect(screen.getByRole('alert')).not.toHaveTextContent('ab806c63-6b08-460b-bd2a-f3f6d2b07116')
  expect(loadLatest).not.toHaveBeenCalled()
})

it('ignores a late failure after the submission epoch changes', async () => {
  const pending = deferred<void>()
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  const view = render(<ProjectFormDialog open project={project} draftSession="edit-1" submissionEpoch="i1:edit-1" onOpenChange={onOpenChange} onSubmit={() => pending.promise} />)
  await user.click(screen.getByRole('button', { name: '保存' }))
  view.rerender(<ProjectFormDialog open project={project} draftSession="edit-1" submissionEpoch="i2:edit-1" onOpenChange={onOpenChange} onSubmit={() => pending.promise} />)
  pending.reject(new ApiClientError('旧实例冲突', 409))
  await Promise.resolve(); await Promise.resolve()
  expect(screen.queryByText(/旧实例冲突/)).not.toBeInTheDocument()
  expect(onOpenChange).not.toHaveBeenCalled()
})

it('ignores a late conflict refresh after a new form session opens', async () => {
  const latest = deferred<ProjectView>()
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  const view = render(<ProjectFormDialog open project={project} draftSession="edit-old" submissionEpoch="i1:old" onOpenChange={onOpenChange} onSubmit={vi.fn().mockRejectedValue(new ApiClientError('冲突', 409, 'REVISION_CONFLICT'))} onLoadLatest={() => latest.promise} />)
  await user.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '正在保存…' })).toBeDisabled())
  view.rerender(<ProjectFormDialog open project={{ ...project, name: '新表单' } as ProjectView} draftSession="edit-new" submissionEpoch="i1:new" onOpenChange={onOpenChange} onSubmit={vi.fn()} />)
  latest.resolve({ ...project, name: '旧请求最新值', managementRevision: 4 } as ProjectView)
  await Promise.resolve(); await Promise.resolve()
  expect(screen.queryByText(/旧请求最新值/)).not.toBeInTheDocument()
  expect(screen.getByLabelText('项目名称')).toHaveValue('新表单')
})

it('does not let an old close guard close a replacement session', async () => {
  const leave = deferred<boolean>()
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  const view = render(<ProjectFormDialog open project={project} draftSession="edit-old" onOpenChange={onOpenChange} onSubmit={vi.fn()} onRequestClose={() => leave.promise} />)
  await user.click(screen.getByRole('button', { name: '取消' }))
  view.rerender(<ProjectFormDialog open project={{ ...project, name: '新表单' } as ProjectView} draftSession="edit-new" onOpenChange={onOpenChange} onSubmit={vi.fn()} onRequestClose={() => leave.promise} />)
  leave.resolve(true)
  await Promise.resolve(); await Promise.resolve()
  expect(onOpenChange).not.toHaveBeenCalled()
})

it('makes fields readonly while recovering an unknown result', () => {
  render(<ProjectFormDialog open project={project} draftSession="recover" recoveryPending onOpenChange={vi.fn()} onSubmit={vi.fn()} />)
  expect(screen.getByLabelText('项目名称')).toHaveAttribute('readonly')
  expect(screen.getByLabelText('项目描述')).toHaveAttribute('readonly')
  expect(screen.getByText('上次保存结果尚未确认，先核对结果后再修改。')).toBeVisible()
  expect(screen.getByRole('button', { name: '核对保存结果' })).toBeEnabled()
})

function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; return { promise: new Promise<T>((yes, no) => { resolve = yes; reject = no }), resolve, reject } }

it.each([
  new ApiClientError('resource ab806c63-6b08-460b-bd2a-f3f6d2b07116', 500, 'INTERNAL_ERROR'),
  new ApiClientError('resource ab806c63-6b08-460b-bd2a-f3f6d2b07116', 409, 'PROJECT_NAME_CONFLICT', { fields: { name: 'ab806c63-6b08-460b-bd2a-f3f6d2b07116' } }),
])('presents server failure without internal identity while keeping the project draft', async error => {
  const id = 'ab806c63-6b08-460b-bd2a-f3f6d2b07116'
  render(<ProjectFormDialog open project={{ ...project, projectId: id }} draftSession="identity" onOpenChange={vi.fn()} onSubmit={vi.fn().mockRejectedValue(error)}/>)
  await userEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
  const presentation = [document.body.textContent, ...[...document.body.querySelectorAll('*')].flatMap(element => ['title', 'placeholder', 'aria-label', 'aria-description'].map(name => element.getAttribute(name) ?? ''))].join('\n')
  expect(presentation).not.toContain(id)
  expect(screen.getByLabelText('项目名称')).toHaveValue('原项目')
})

it('preserves a UUID chosen as the business project name in a conflict result', async () => {
  const businessName = '977092e7-5e47-401a-b028-3c86d3a0fa80'
  const latest = { ...project, name: businessName, managementRevision: 3 }
  render(<ProjectFormDialog open project={project} draftSession="business-uuid" onOpenChange={vi.fn()} onSubmit={vi.fn().mockRejectedValue(new ApiClientError('internal', 409, 'REVISION_CONFLICT'))} onLoadLatest={vi.fn().mockResolvedValue(latest)}/>)
  await userEvent.click(screen.getByRole('button', { name: '保存' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(businessName)
  await userEvent.click(screen.getByRole('button', { name: '基于最新内容重新编辑' }))
  expect(screen.getByLabelText('项目名称')).toHaveValue(businessName)
})
