import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { startTransition, Suspense, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { DataTableFormDialog } from './DataTableFormDialog'

afterEach(cleanup)

it('renders the gallery create-table structure without changing the data limits', () => {
  render(<DataTableFormDialog open mode="create" sessionKey="gallery" onOpenChange={vi.fn()} onSubmit={vi.fn()} />)
  const dialog=screen.getByRole('dialog',{name:'新建数据表'})
  expect(dialog).toHaveClass('max-w-[32.5rem]')
  expect(dialog).toHaveClass('[&_[data-slot=dialog-title]]:text-[28px]')
  expect(screen.getByText('*')).toHaveAttribute('aria-hidden','true')
  expect(screen.getByText('创建后即可维护本地记录，后续可按需配置数据来源。')).toBeVisible()
  expect(screen.queryByText(/来源未配置|不能新增/)).not.toBeInTheDocument()
})

it('accepts the schema limits as Unicode code points without native UTF-16 truncation',async()=>{
  const user=userEvent.setup(),submit=vi.fn().mockResolvedValue(undefined),name='😀'.repeat(120),description='😀'.repeat(1000)
  render(<DataTableFormDialog open mode="create" sessionKey="unicode-limits" onOpenChange={vi.fn()} onSubmit={submit}/>)
  await user.type(screen.getByLabelText('数据表名称'),name);await user.type(screen.getByLabelText('用途说明（可选）'),description)
  await user.click(screen.getByRole('button',{name:'创建数据表'}))
  await waitFor(()=>expect(submit).toHaveBeenCalledWith({name,description}))
})

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

it('lets the application guard own dirty close and reports draft changes', async () => {
  const onDirtyChange = vi.fn(), onRequestClose = vi.fn().mockResolvedValue(false), onOpenChange = vi.fn()
  render(<DataTableFormDialog open mode="create" sessionKey="guard" onSubmit={vi.fn()} onOpenChange={onOpenChange} onDirtyChange={onDirtyChange} onRequestClose={onRequestClose} />)
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  expect(onDirtyChange).toHaveBeenLastCalledWith(true)
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(onRequestClose).toHaveBeenCalledOnce()
  expect(onOpenChange).not.toHaveBeenCalled()
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

it('revokes resolver submission when the form closes or becomes readonly before resolution', async () => {
  for (const change of [{ open: false }, { readonly: true }]) {
    const onSubmit = vi.fn()
    const props = { open: true, mode: 'edit' as const, sessionKey: 'a', initialValues: { name: 'A', description: '' }, onSubmit, onOpenChange: vi.fn() }
    const view = render(<DataTableFormDialog {...props} />)
    fireEvent.submit(view.container.ownerDocument.querySelector('#data-table-form')!)
    view.rerender(<DataTableFormDialog {...props} {...change} />)
    await waitFor(() => expect(screen.queryByText('正在保存…')).not.toBeInTheDocument())
    expect(onSubmit).not.toHaveBeenCalled()
    view.unmount()
  }
})

it('prevents duplicate submit events before React commits the saving state', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  render(<DataTableFormDialog open mode="edit" sessionKey="a" initialValues={{ name: 'A', description: '' }} onSubmit={onSubmit} onOpenChange={vi.fn()} />)
  const form = document.querySelector<HTMLFormElement>('#data-table-form')!
  fireEvent.submit(form); fireEvent.submit(form)
  await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
})

it('retains the draft on reconnect and offers recovery while inputs are frozen', async () => {
  const onRecover = vi.fn().mockResolvedValue(undefined)
  const props = { open: true, mode: 'edit' as const, sessionKey: 'a', submissionEpoch: 'i1', initialValues: { name: 'A', description: '' }, onSubmit: vi.fn(), onOpenChange: vi.fn(), onRecover }
  const view = render(<DataTableFormDialog {...props} />)
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  view.rerender(<DataTableFormDialog {...props} submissionEpoch="i2" recoveryPending />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('A草稿')
  expect(screen.getByLabelText('数据表名称')).toHaveAttribute('readonly')
  await userEvent.click(screen.getByRole('button', { name: '核对保存结果' }))
  expect(onRecover).toHaveBeenCalledOnce()
  expect(props.onSubmit).not.toHaveBeenCalled()
})

it('reports local saving to the parent and exposes parent error actions', async () => {
  let finish!:()=>void
  const onSavingChange=vi.fn(),pending=new Promise<void>(resolve=>{finish=resolve})
  render(<DataTableFormDialog open mode="edit" sessionKey="saving" initialValues={{name:'A',description:''}} error="冲突" errorActions={<button>重新载入</button>} onSavingChange={onSavingChange} onOpenChange={vi.fn()} onSubmit={()=>pending}/>)
  expect(screen.getByRole('button',{name:'重新载入'})).toBeVisible()
  fireEvent.submit(document.querySelector('#data-table-form')!)
  expect(onSavingChange).toHaveBeenLastCalledWith(true);finish()
  await waitFor(()=>expect(onSavingChange).toHaveBeenLastCalledWith(false))
})

it('does not allow a pending recovery to be discarded without an external guard', async () => {
  const close=vi.fn()
  render(<DataTableFormDialog open mode="edit" sessionKey="recovery" recoveryPending initialValues={{name:'A',description:''}} onOpenChange={close} onSubmit={vi.fn()}/>)
  await userEvent.click(screen.getByRole('button',{name:'取消'}))
  expect(close).not.toHaveBeenCalled();expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

it('does not apply a stale close approval after saving has started', async () => {
  let approve!: (allowed: boolean) => void, finish!: () => void
  const onRequestClose = vi.fn(() => new Promise<boolean>(resolve => { approve = resolve }))
  const onSubmit = vi.fn(() => new Promise<void>(resolve => { finish = resolve })), onOpenChange = vi.fn()
  render(<DataTableFormDialog open mode="create" sessionKey="a" onOpenChange={onOpenChange} onRequestClose={onRequestClose} onSubmit={onSubmit} />)
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  await userEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
  approve(true)
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  expect(onOpenChange).not.toHaveBeenCalled()
  finish()
  await waitFor(() => expect(screen.getByRole('button', { name: '创建数据表' })).toBeEnabled())
})
