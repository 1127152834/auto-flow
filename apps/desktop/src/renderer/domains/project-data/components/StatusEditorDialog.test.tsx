import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { startTransition, Suspense, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { statusFormSchema } from '../status-form-schema'
import { StatusEditorDialog } from './StatusEditorDialog'

afterEach(cleanup)

it('canonicalizes create values, submits once, and leaves closing to parent', async () => {
  let finish!: () => void
  const submit = vi.fn(() => new Promise<void>(resolve => { finish = resolve }))
  const close = vi.fn(); const user = userEvent.setup()
  render(<StatusEditorDialog open mode="create" sessionKey="w:p:create" onOpenChange={close} onSubmit={submit} />)
  await user.type(screen.getByLabelText('状态名称'), '  待处理😀  ')
  await user.clear(screen.getByLabelText('状态颜色')); await user.type(screen.getByLabelText('状态颜色'), '#AABBCC')
  await user.clear(screen.getByLabelText('显示顺序')); await user.type(screen.getByLabelText('显示顺序'), '2')
  expect(screen.getByLabelText('状态名称')).toHaveValue('  待处理😀  ')
  await user.click(screen.getByRole('button', { name: '创建状态' }))
  await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
  expect(submit).toHaveBeenCalledWith({ name: '待处理😀', color: '#aabbcc', order: 2 })
  expect(close).not.toHaveBeenCalled(); finish()
  await waitFor(() => expect(screen.getByRole('button', { name: '创建状态' })).toBeEnabled())
})

it('edit submits only changed fields and preserves dirty draft on refresh and failure', async () => {
  const submit = vi.fn().mockRejectedValue(new Error('版本冲突')); const dirty = vi.fn(); const user = userEvent.setup()
  const props = { open: true, mode: 'edit' as const, sessionKey: 'w:p:s:a', onOpenChange: vi.fn(), onSubmit: submit, onDirtyChange: dirty }
  const view = render(<StatusEditorDialog {...props} initialValues={{ name: '待处理', color: '#a86f4c', order: 1 }} />)
  await user.clear(screen.getByLabelText('状态名称')); await user.type(screen.getByLabelText('状态名称'), '完成')
  view.rerender(<StatusEditorDialog {...props} initialValues={{ name: '后台值', color: '#ffffff', order: 9 }} />)
  expect(screen.getByLabelText('状态名称')).toHaveValue('完成')
  await user.click(screen.getByRole('button', { name: '保存修改' }))
  expect(submit).toHaveBeenCalledWith({ name: '完成' })
  expect(await screen.findByRole('alert')).toHaveTextContent('版本冲突')
  expect(dirty).toHaveBeenCalledWith(true)
})

it('validates fields and supports preset colors without a system picker', async () => {
  const submit = vi.fn(); const user = userEvent.setup()
  render(<StatusEditorDialog open mode="create" sessionKey="a" onOpenChange={vi.fn()} onSubmit={submit} />)
  expect(screen.queryByLabelText(/系统颜色/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '选择颜色 #486b52' }))
  expect(screen.getByLabelText('状态颜色')).toHaveValue('#486b52')
  await user.clear(screen.getByLabelText('显示顺序')); await user.type(screen.getByLabelText('显示顺序'), '-1')
  await user.click(screen.getByRole('button', { name: '创建状态' }))
  expect(await screen.findByText('请输入状态名称')).toBeVisible()
  expect(await screen.findByText('顺序不能小于 0')).toBeVisible()
  expect(submit).not.toHaveBeenCalled()
})

it('guards dirty close and locks the confirmation while saving', async () => {
  const close = vi.fn(); const user = userEvent.setup()
  const props = { open: true, mode: 'create' as const, sessionKey: 'a', onOpenChange: close, onSubmit: vi.fn() }
  const view = render(<StatusEditorDialog {...props} />)
  await user.type(screen.getByLabelText('状态名称'), '草稿'); await user.click(screen.getByRole('button', { name: '取消' }))
  expect(screen.getByRole('button', { name: '继续编辑' })).toHaveFocus()
  view.rerender(<StatusEditorDialog {...props} saving />)
  expect(screen.getByRole('button', { name: '放弃修改' })).toBeDisabled()
  await user.keyboard('{Escape}'); expect(screen.getByRole('alertdialog')).toBeVisible(); expect(close).not.toHaveBeenCalled()
})

it('ignores a late failure after switching to a new session', async () => {
  let rejectA!: (reason: unknown) => void
  const pending = new Promise<void>((_, reject) => { rejectA = reject })
  const props = { open: true, mode: 'edit' as const, onOpenChange: vi.fn() }
  const view = render(<StatusEditorDialog {...props} sessionKey="a" initialValues={{ name:'A',color:'#111111',order:0 }} onSubmit={() => pending} />)
  await userEvent.clear(screen.getByLabelText('状态名称')); await userEvent.type(screen.getByLabelText('状态名称'), 'A changed')
  await userEvent.click(screen.getByRole('button', { name:'保存修改' }))
  view.rerender(<StatusEditorDialog {...props} sessionKey="b" initialValues={{ name:'B',color:'#222222',order:1 }} onSubmit={vi.fn()} />)
  rejectA(new Error('旧会话失败')); await Promise.resolve(); await Promise.resolve()
  expect(screen.getByLabelText('状态名称')).toHaveValue('B')
  expect(screen.queryByText('旧会话失败')).not.toBeInTheDocument()
})

it('does not invalidate the active request for a suspended render that never commits', async () => {
  let finish!: () => void
  const pending = new Promise<void>(resolve => { finish = resolve }); const submit = vi.fn(() => pending); const never = new Promise<void>(() => undefined)
  function Block({ session }: { session: string }) { if (session === 'b') throw never; return null }
  function Harness() {
    const [session,setSession]=useState('a')
    return <><button onClick={() => startTransition(() => setSession('b'))}>切换</button><Suspense fallback={<span>载入</span>}><StatusEditorDialog open mode="edit" sessionKey={session} initialValues={{ name:session.toUpperCase(),color:'#111111',order:0 }} onOpenChange={vi.fn()} onSubmit={submit}/><Block session={session}/></Suspense></>
  }
  render(<Harness />); await userEvent.clear(screen.getByLabelText('状态名称')); await userEvent.type(screen.getByLabelText('状态名称'), 'A changed'); await userEvent.click(screen.getByRole('button',{name:'保存修改'})); await waitFor(() => expect(submit).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByRole('button',{name:'切换',hidden:true})); expect(screen.getByLabelText('状态名称')).toHaveValue('A changed'); finish()
  await waitFor(() => expect(screen.getByRole('button',{name:'保存修改'})).toBeEnabled())
})

it('disables edit submission when normalized values are unchanged', async () => {
  const submit=vi.fn(); const user=userEvent.setup()
  render(<StatusEditorDialog open mode="edit" sessionKey="a" initialValues={{name:'Ready',color:'#aabbcc',order:1}} onOpenChange={vi.fn()} onSubmit={submit}/>)
  const button=screen.getByRole('button',{name:'保存修改'}); expect(button).toBeDisabled()
  const name=screen.getByLabelText('状态名称'); await user.clear(name); await user.type(name,'  Ready  ')
  const color=screen.getByLabelText('状态颜色'); await user.clear(color); await user.type(color,'#AABBCC')
  expect(button).toBeDisabled(); await user.keyboard('{Enter}'); expect(submit).not.toHaveBeenCalled()
})

it('keeps an invalid empty edit dirty across refresh and allows validation', async () => {
  const dirty=vi.fn(); const submit=vi.fn(); const user=userEvent.setup()
  const props={open:true,mode:'edit' as const,sessionKey:'a',onOpenChange:vi.fn(),onSubmit:submit,onDirtyChange:dirty}
  const view=render(<StatusEditorDialog {...props} initialValues={{name:'Ready',color:'#aabbcc',order:1}}/>)
  await user.clear(screen.getByLabelText('状态名称')); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(true))
  view.rerender(<StatusEditorDialog {...props} initialValues={{name:'Server refresh',color:'#112233',order:2}}/>)
  expect(screen.getByLabelText('状态名称')).toHaveValue('')
  const save=screen.getByRole('button',{name:'保存修改'}); expect(save).toBeEnabled(); await user.click(save)
  expect(await screen.findByText('请输入状态名称')).toBeVisible(); expect(submit).not.toHaveBeenCalled()
})

it('clears dirty state on external close, session change, and unmount', async () => {
  const dirty=vi.fn(); const props={mode:'edit' as const,onOpenChange:vi.fn(),onSubmit:vi.fn(),onDirtyChange:dirty}
  const view=render(<StatusEditorDialog {...props} open sessionKey="a" initialValues={{name:'A',color:'#111111',order:0}}/>)
  await userEvent.clear(screen.getByLabelText('状态名称')); await userEvent.type(screen.getByLabelText('状态名称'),'changed'); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(true))
  view.rerender(<StatusEditorDialog {...props} open={false} sessionKey="a" initialValues={{name:'A',color:'#111111',order:0}}/>); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(false))
  view.rerender(<StatusEditorDialog {...props} open sessionKey="b" initialValues={{name:'B',color:'#222222',order:1}}/>); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(false))
  view.unmount(); expect(dirty).toHaveBeenLastCalledWith(false)
})

it('keeps every edit control and submission disabled when readonly', async () => {
  const submit = vi.fn(); const user = userEvent.setup()
  render(<StatusEditorDialog open readonly mode="edit" sessionKey="readonly" initialValues={{name:'Ready',color:'#aabbcc',order:1}} onOpenChange={vi.fn()} onSubmit={submit}/>)
  expect(screen.getByLabelText('状态名称')).toHaveAttribute('readonly')
  expect(screen.getByLabelText('状态颜色')).toHaveAttribute('readonly')
  expect(screen.getByLabelText('显示顺序')).toHaveAttribute('readonly')
  expect(screen.getByRole('button',{name:'选择颜色 #486b52'})).toBeDisabled()
  expect(screen.getByRole('button',{name:'保存修改'})).toBeDisabled()
  await user.keyboard('{Enter}')
  expect(submit).not.toHaveBeenCalled()
})

it('counts status names by Unicode code point at the 120 character boundary', () => {
  const base = { color: '#aabbcc', order: 0 }
  expect(statusFormSchema.safeParse({ ...base, name: '😀'.repeat(120) }).success).toBe(true)
  expect(statusFormSchema.safeParse({ ...base, name: '😀'.repeat(121) }).success).toBe(false)
})

it('accepts only nonnegative safe integer status orders', () => {
  const base = { name: 'Ready', color: '#aabbcc' }
  expect(statusFormSchema.safeParse({ ...base, order: Number.MAX_SAFE_INTEGER }).success).toBe(true)
  expect(statusFormSchema.safeParse({ ...base, order: Number.MAX_SAFE_INTEGER + 1 }).success).toBe(false)
  expect(statusFormSchema.safeParse({ ...base, order: Number.NaN }).success).toBe(false)
})
