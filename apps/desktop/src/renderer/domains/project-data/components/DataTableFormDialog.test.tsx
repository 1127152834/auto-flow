import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { startTransition, Suspense, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { DataTableFormDialog } from './DataTableFormDialog'

afterEach(cleanup)

it('validates, trims, submits once, and leaves closing to the parent', async () => {
  let finish!: () => void
  const pending = new Promise<void>(resolve => { finish = resolve })
  const submit = vi.fn(() => pending)
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  render(<DataTableFormDialog open mode="create" sessionKey="workspace:project:create:a" onOpenChange={onOpenChange} onSubmit={submit} />)
  await user.type(screen.getByLabelText('数据表名称'), '  客户😀  ')
  await user.dblClick(screen.getByRole('button', { name: '创建数据表' }))
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  expect(submit).toHaveBeenCalledWith({ name: '客户😀', description: '' })
  expect(onOpenChange).not.toHaveBeenCalled()
  await user.keyboard('{Escape}')
  expect(onOpenChange).not.toHaveBeenCalled()
  finish()
  await waitFor(() => expect(screen.getByRole('button', { name: '创建数据表' })).toBeEnabled())
  expect(onOpenChange).not.toHaveBeenCalled()
})

it('preserves a dirty draft across refreshed initial values and server errors', async () => {
  const user = userEvent.setup()
  const props = { open: true, mode: 'edit' as const, sessionKey: 'workspace:project:table:a', onOpenChange: vi.fn(), onSubmit: vi.fn().mockRejectedValue(new Error('冲突')) }
  const view = render(<DataTableFormDialog {...props} initialValues={{ name: '原名称', description: '原说明' }} />)
  await user.clear(screen.getByLabelText('数据表名称'))
  await user.type(screen.getByLabelText('数据表名称'), '我的草稿')
  view.rerender(<DataTableFormDialog {...props} initialValues={{ name: '后台名称', description: '后台说明' }} error="数据表已被修改" />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('我的草稿')
  expect(screen.getByRole('alert')).toHaveTextContent('数据表已被修改')
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('冲突')
  expect(screen.getByLabelText('数据表名称')).toHaveValue('我的草稿')
})

it('confirms every dirty close path and focuses continue editing by default', async () => {
  const user = userEvent.setup()
  const onOpenChange = vi.fn()
  render(<DataTableFormDialog open mode="create" sessionKey="workspace:project:create:a" onOpenChange={onOpenChange} onSubmit={vi.fn()} />)
  await user.type(screen.getByLabelText('数据表名称'), '草稿')
  await user.click(screen.getByRole('button', { name: '取消' }))
  expect(screen.getByRole('alertdialog')).toBeVisible()
  expect(screen.getByRole('button', { name: '继续编辑' })).toHaveFocus()
  await user.click(screen.getByRole('button', { name: '继续编辑' }))
  await user.keyboard('{Escape}')
  expect(screen.getByRole('alertdialog')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '放弃修改' }))
  expect(onOpenChange).toHaveBeenCalledWith(false)
})

it('allows opening but disables editing and creation while readonly', () => {
  render(<DataTableFormDialog open mode="edit" sessionKey="workspace:project:table:readonly" readonly initialValues={{ name: '归档表', description: '' }} onOpenChange={vi.fn()} onSubmit={vi.fn()} />)
  expect(screen.getByLabelText('数据表名称')).toHaveAttribute('readonly')
  expect(screen.getByRole('button', { name: '保存修改' })).toBeDisabled()
})

it('ignores a late result after switching from session A to B', async () => {
  let rejectA!: (reason: unknown) => void
  const pendingA = new Promise<void>((_, reject) => { rejectA = reject })
  const view = render(<DataTableFormDialog open mode="edit" sessionKey="workspace:project:table:a" initialValues={{ name: 'A', description: '' }} onOpenChange={vi.fn()} onSubmit={() => pendingA} />)
  await userEvent.click(screen.getByRole('button', { name: '保存修改' }))
  view.rerender(<DataTableFormDialog open mode="edit" sessionKey="workspace:project:table:b" initialValues={{ name: 'B', description: '' }} onOpenChange={vi.fn()} onSubmit={vi.fn()} />)
  rejectA(new Error('旧会话失败'))
  await Promise.resolve(); await Promise.resolve()
  expect(screen.getByLabelText('数据表名称')).toHaveValue('B')
  expect(screen.queryByText('旧会话失败')).not.toBeInTheDocument()
})

it('resets a dirty closed draft when a new session opens', async () => {
  const props = { mode: 'edit' as const, onOpenChange: vi.fn(), onSubmit: vi.fn() }
  const view = render(<DataTableFormDialog {...props} open sessionKey="a" initialValues={{ name: 'A', description: '' }} />)
  await userEvent.clear(screen.getByLabelText('数据表名称')); await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  view.rerender(<DataTableFormDialog {...props} open={false} sessionKey="a" initialValues={{ name: 'A', description: '' }} />)
  view.rerender(<DataTableFormDialog {...props} open sessionKey="b" initialValues={{ name: 'B', description: '' }} />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('B')
})

it('locks an already-open discard confirmation when saving becomes true', async () => {
  const props = { open: true, mode: 'create' as const, sessionKey: 'a', onOpenChange: vi.fn(), onSubmit: vi.fn() }
  const view = render(<DataTableFormDialog {...props} />)
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  view.rerender(<DataTableFormDialog {...props} saving />)
  expect(screen.getByRole('button', { name: '放弃修改' })).toBeDisabled()
  await userEvent.keyboard('{Escape}')
  expect(screen.getByRole('alertdialog')).toBeVisible()
})

it('does not invalidate session A when a suspended session B render never commits', async () => {
  let finishA!: () => void
  const pendingA = new Promise<void>(resolve => { finishA = resolve })
  const submitA = vi.fn(() => pendingA)
  const never = new Promise<void>(() => undefined)
  let renderedB = false
  function SuspendedB({ session }: { session: string }) {
    if (session === 'b') { renderedB = true; throw never }
    return null
  }
  function Harness() {
    const [session, setSession] = useState('a')
    return <><button onClick={() => { startTransition(() => setSession('b')) }}>切换会话</button><Suspense fallback={<span>载入 B</span>}><DataTableFormDialog open mode="edit" sessionKey={session} initialValues={{ name: session.toUpperCase(), description: '' }} onOpenChange={vi.fn()} onSubmit={submitA} /><SuspendedB session={session} /></Suspense></>
  }
  render(<Harness />)
  await userEvent.click(screen.getByRole('button', { name: '保存修改' }))
  await waitFor(() => expect(submitA).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByRole('button', { name: '切换会话', hidden: true }))
  expect(renderedB).toBe(true)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('A')
  finishA()
  await waitFor(() => expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled())
})
