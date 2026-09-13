import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { TableSettingsForm } from './TableSettingsForm'

afterEach(cleanup)
const initialValues = { name: '资料库', description: '保存整理后的文章资料' }
const props = () => ({ sessionKey: 'workspace:table:edit', initialValues, onSubmit: vi.fn().mockResolvedValue(undefined), onCancel: vi.fn() })
const changeName = (name: string) => fireEvent.change(screen.getByLabelText('数据表名称'), { target: { value: name } })

it('renders page-local basic information, labelled fields and cancel/save without a modal', () => {
  render(<TableSettingsForm {...props()} />)
  expect(screen.getByRole('form', { name: '基本信息' })).toBeVisible()
  expect(screen.getByRole('heading', { name: '基本信息', level: 3 })).toBeVisible()
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByLabelText('数据表名称')).toHaveValue(initialValues.name)
  expect(screen.getByLabelText('用途说明')).toHaveValue(initialValues.description)
  expect(screen.getByRole('button', { name: '保存设置' })).toBeDisabled()
  expect(screen.getByText('最多 1000 个字符')).toBeVisible()
})

it('validates every field, focuses the first error and uses Unicode code-point limits', async () => {
  const p = props(); render(<TableSettingsForm {...p} />)
  changeName(' ')
  fireEvent.change(screen.getByLabelText('用途说明'), { target: { value: '😀'.repeat(1001) } })
  fireEvent.submit(screen.getByRole('form'))
  expect(await screen.findByText('请输入数据表名称')).toBeVisible()
  expect(screen.getByText('数据表描述最多 1000 个字符')).toBeVisible()
  expect(screen.getByLabelText('数据表名称')).toHaveFocus()
  expect(p.onSubmit).not.toHaveBeenCalled()
  changeName(`  ${'😀'.repeat(120)}  `)
  fireEvent.change(screen.getByLabelText('用途说明'), { target: { value: '😀'.repeat(1000) } })
  fireEvent.submit(screen.getByRole('form'))
  await waitFor(() => expect(p.onSubmit).toHaveBeenCalledWith({ name: '😀'.repeat(120), description: '😀'.repeat(1000) }))
  expect(screen.getByLabelText('数据表名称')).not.toHaveAttribute('maxlength')
})

it('keeps dirty values across refresh, readonly and same-workspace reconnect, but resets an explicit session', () => {
  const p = props(), dirty = vi.fn(); const view = render(<TableSettingsForm {...p} onDirtyChange={dirty} />)
  changeName('我的草稿')
  view.rerender(<TableSettingsForm {...p} initialValues={{ name: '后台名称', description: '后台说明' }} submissionEpoch="new-instance" readonly onDirtyChange={dirty} />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('我的草稿')
  expect(dirty).toHaveBeenLastCalledWith(true)
  view.rerender(<TableSettingsForm {...p} sessionKey="other-workspace:table" initialValues={{ name: '另一表', description: '' }} onDirtyChange={dirty} />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('另一表')
  expect(dirty).toHaveBeenLastCalledWith(false)
})

it('refreshes clean fields and reports returning to the original values as clean', () => {
  const p = props(), dirty = vi.fn(), view = render(<TableSettingsForm {...p} onDirtyChange={dirty} />)
  view.rerender(<TableSettingsForm {...p} initialValues={{ name: '更新', description: '' }} onDirtyChange={dirty} />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('更新')
  changeName('暂改'); changeName('更新')
  expect(dirty).toHaveBeenLastCalledWith(false)
})

it.each(['readonly', 'saving', 'recoveryPending'] as const)('guards native submit and preserves values while %s', async flag => {
  const p = props(), view = render(<TableSettingsForm {...p} />); changeName('草稿')
  view.rerender(<TableSettingsForm {...p} {...{ [flag]: true }} />)
  expect(screen.getByLabelText('数据表名称')).toHaveAttribute('readonly')
  expect(screen.getByRole('button', { name: '保存设置' })).toBeDisabled()
  fireEvent.submit(screen.getByRole('form'))
  await act(async () => {})
  expect(p.onSubmit).not.toHaveBeenCalled()
  expect(screen.getByLabelText('数据表名称')).toHaveValue('草稿')
  if (flag !== 'readonly') expect(screen.getByRole('button', { name: '取消更改' })).toBeDisabled()
})

it('submits once and isolates an old rejected response after switching session', async () => {
  let reject!: (error: Error) => void
  const p = props(); p.onSubmit.mockImplementation(() => new Promise((_, fail) => { reject = fail }))
  const view = render(<TableSettingsForm {...p} />); changeName('A 草稿')
  fireEvent.submit(screen.getByRole('form')); fireEvent.submit(screen.getByRole('form'))
  await waitFor(() => expect(p.onSubmit).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button', { name: '取消更改' })).toBeDisabled()
  view.rerender(<TableSettingsForm {...props()} sessionKey="B" initialValues={{ name: 'B', description: '' }} />)
  await act(async () => reject(new Error('旧会话失败')))
  expect(screen.queryByText('旧会话失败')).toBeNull()
  expect(screen.getByLabelText('数据表名称')).toHaveValue('B')
})

it('keeps an uncertain draft frozen across reconnect and recovers only on explicit action', async () => {
  const p = props(), recover = vi.fn().mockRejectedValue(new Error('仍无法确认'))
  const view = render(<TableSettingsForm {...p} />); changeName('未知草稿')
  view.rerender(<TableSettingsForm {...p} submissionEpoch="reconnected" recoveryPending onRecover={recover} />)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('未知草稿')
  expect(recover).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '查询保存结果' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('仍无法确认')
  expect(screen.getByRole('button', { name: '保存设置' })).toBeDisabled()
  expect(p.onCancel).not.toHaveBeenCalled()
})

it('leaves dirty cancel and confirmed save lifecycle to the parent and clears callbacks on unmount', async () => {
  const p = props(), dirty = vi.fn(), saving = vi.fn()
  const view = render(<TableSettingsForm {...p} onDirtyChange={dirty} onSavingChange={saving} />)
  changeName('草稿')
  await userEvent.click(screen.getByRole('button', { name: '取消更改' }))
  expect(p.onCancel).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('草稿')
  view.unmount()
  expect(dirty).toHaveBeenLastCalledWith(false)
  expect(saving).toHaveBeenLastCalledWith(false)
})

it('isolates a reconnect response while an outer save lock remains authoritative', async () => {
  let reject!: (error: Error) => void
  const p = props(); p.onSubmit.mockImplementation(() => new Promise((_, fail) => { reject = fail }))
  const view = render(<TableSettingsForm {...p} />); changeName('重连前草稿')
  fireEvent.submit(screen.getByRole('form'))
  await waitFor(() => expect(p.onSubmit).toHaveBeenCalledTimes(1))
  view.rerender(<TableSettingsForm {...p} submissionEpoch="new-instance" saving recoveryPending />)
  await act(async () => reject(new Error('旧实例失败')))
  expect(screen.queryByText('旧实例失败')).toBeNull()
  expect(screen.getByLabelText('数据表名称')).toHaveValue('重连前草稿')
  expect(screen.getByRole('button', { name: '取消更改' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '保存设置' })).toBeDisabled()
})

it('rechecks readonly after async validation and does not call the business command', async () => {
  const p = props(), view = render(<TableSettingsForm {...p} />); changeName('草稿')
  fireEvent.submit(screen.getByRole('form'))
  view.rerender(<TableSettingsForm {...p} readonly />)
  await act(async () => {})
  expect(p.onSubmit).not.toHaveBeenCalled()
})

it('shows parent recovery actions and retains draft when an awaited submit resolves without confirmation', async () => {
  const p = props(), view = render(<TableSettingsForm {...p} />); changeName('结果未知的草稿')
  fireEvent.submit(screen.getByRole('form'))
  await waitFor(() => expect(p.onSubmit).toHaveBeenCalledTimes(1))
  view.rerender(<TableSettingsForm {...p} recoveryPending error="等待恢复" errorActions={<button type="button">查看错误详情</button>} />)
  expect(screen.getByRole('alert')).toHaveTextContent('等待恢复')
  expect(screen.getByRole('button', { name: '查看错误详情' })).toBeVisible()
  expect(screen.getByLabelText('数据表名称')).toHaveValue('结果未知的草稿')
  expect(screen.getByText('保存结果尚未确认，请先查询保存结果。')).toBeVisible()
})
