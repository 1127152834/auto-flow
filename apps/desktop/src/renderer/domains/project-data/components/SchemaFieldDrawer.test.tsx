import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SchemaFieldDrawer } from './SchemaFieldDrawer'

afterEach(cleanup)
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture = vi.fn()
  HTMLElement.prototype.releasePointerCapture = vi.fn()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
const field = { ref: { projectId:'00000000-0000-0000-0000-000000000001', tableId:'00000000-0000-0000-0000-000000000002', datasetGeneration:'00000000-0000-0000-0000-000000000003', fieldId:'00000000-0000-0000-0000-000000000004' }, key:'email', name:'邮箱', type:'string' as const, required:false, writable:true, formula:false, validation:{}, fieldRevision:1 }

it('renders as a drawer and applies a candidate locally without closing it', async () => {
  const apply=vi.fn(), close=vi.fn(), user=userEvent.setup()
  render(<SchemaFieldDrawer open sessionKey="new" onApply={apply} onOpenChange={close}/>)
  expect(screen.getByRole('dialog')).toHaveAttribute('data-placement','drawer')
  await user.type(screen.getByLabelText('显示名称'),' Email '); await user.type(screen.getByLabelText('字段键'),' email ')
  await user.click(screen.getByLabelText('现有记录默认值值状态')); await user.click(screen.getByRole('option',{name:'清空'}))
  await user.click(screen.getByRole('button',{name:'应用到草稿'}))
  await waitFor(()=>expect(apply).toHaveBeenCalledWith({definition:{key:'email',name:'Email',type:'string',required:false,validation:{}},existingRecordDefault:null}))
  expect(close).not.toHaveBeenCalled()
})

it('preserves an omitted default instead of manufacturing null', async () => {
  const apply=vi.fn(), user=userEvent.setup()
  render(<SchemaFieldDrawer open sessionKey="missing" onApply={apply} onOpenChange={vi.fn()}/>)
  await user.type(screen.getByLabelText('显示名称'),'标题'); await user.type(screen.getByLabelText('字段键'),'title')
  await user.click(screen.getByRole('button',{name:'应用到草稿'}))
  await waitFor(()=>expect(apply).toHaveBeenCalledWith({definition:{key:'title',name:'标题',type:'string',required:false,validation:{}}}))
})

it('locks an existing key and identity type while allowing other edits', async () => {
  const user=userEvent.setup(), apply=vi.fn()
  render(<SchemaFieldDrawer open sessionKey="edit" initialField={field} isIdentityField onApply={apply} onOpenChange={vi.fn()}/>)
  expect(screen.getByLabelText('字段键')).toHaveAttribute('readonly')
  expect(screen.getByLabelText('类型')).toHaveAttribute('aria-readonly','true')
  await user.clear(screen.getByLabelText('显示名称')); await user.type(screen.getByLabelText('显示名称'),'联系邮箱')
  await user.click(screen.getByRole('button',{name:'应用到草稿'}))
  expect(apply).toHaveBeenCalledWith({definition:{key:'email',name:'联系邮箱',type:'string',required:false,validation:{}}})
})

it('guards dirty cancellation and never applies the abandoned candidate', async () => {
  const apply=vi.fn(), close=vi.fn(), user=userEvent.setup()
  render(<SchemaFieldDrawer open sessionKey="dirty" initialField={field} onApply={apply} onOpenChange={close}/>)
  await user.type(screen.getByLabelText('显示名称'),' draft'); await user.click(screen.getByRole('button',{name:'取消'}))
  expect(await screen.findByText('放弃未应用的修改？')).toBeVisible(); expect(close).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'放弃修改'}))
  expect(close).toHaveBeenCalledWith(false); expect(apply).not.toHaveBeenCalled()
})

it('keeps dirty input through reconnect and refresh, then resets for a new session', async () => {
  const props={open:true,sessionKey:'A',submissionEpoch:1,initialField:field,onApply:vi.fn(),onOpenChange:vi.fn()}
  const view=render(<SchemaFieldDrawer {...props}/>)
  fireEvent.change(screen.getByLabelText('显示名称'),{target:{value:'草稿'}})
  view.rerender(<SchemaFieldDrawer {...props} submissionEpoch={2} initialField={{...field,name:'服务端'}}/>)
  expect(screen.getByLabelText('显示名称')).toHaveValue('草稿')
  view.rerender(<SchemaFieldDrawer {...props} sessionKey="B" submissionEpoch={2} initialField={{...field,name:'新会话'}}/>)
  await waitFor(()=>expect(screen.getByLabelText('显示名称')).toHaveValue('新会话'))
})

it('keeps protected fields inspectable and disables applying them', () => {
  render(<SchemaFieldDrawer open sessionKey="protected" initialField={{...field,formula:true,writable:false}} onApply={vi.fn()} onOpenChange={vi.fn()}/>)
  expect(screen.getByLabelText('显示名称')).toHaveAttribute('readonly')
  expect(screen.getByRole('button',{name:'应用到草稿'})).toBeDisabled()
})


it('uses the gallery rule selector, required switch and example preview', async () => {
  const user = userEvent.setup(), apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="gallery" initialField={field} onApply={apply} onOpenChange={vi.fn()} />)
  expect(screen.getByRole('switch', { name: '必填' })).toBeVisible()
  expect(screen.queryByLabelText('Python 正则表达式')).toBeNull()
  await user.click(screen.getByLabelText('校验规则'))
  await user.click(screen.getByRole('option', { name: '网址格式' }))
  expect(screen.getByLabelText('示例值预览')).toHaveValue('https://example.com/notes/R013')
  expect(screen.getByText('更改字段类型会清除原有校验规则，需重新选择。')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '应用到草稿' }))
  expect(apply).toHaveBeenCalledWith({ definition: { key: 'email', name: '邮箱', type: 'string', required: false, validation: { pattern: '^https?://[^\\s]+$' } } })
})

it('preserves complete custom rules without guessing a URL preset and allows advanced editing', async () => {
  const user = userEvent.setup(), apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="custom" initialField={{ ...field, validation: { minLength: 3, maxLength: 80, pattern: '^https?://[^\\s]+$' } }} onApply={apply} onOpenChange={vi.fn()} />)
  expect(screen.getByLabelText('校验规则')).toHaveTextContent('自定义规则')
  expect(screen.getByLabelText('最小长度')).toHaveValue('3')
  expect(screen.getByLabelText('最大长度')).toHaveValue('80')
  expect(screen.getByLabelText('Python 正则表达式')).toHaveValue('^https?://[^\\s]+$')
  await user.type(screen.getByLabelText('显示名称'), '新')
  await user.click(screen.getByRole('button', { name: '应用到草稿' }))
  expect(apply).toHaveBeenCalledWith({ definition: { key: 'email', name: '邮箱新', type: 'string', required: false, validation: { minLength: 3, maxLength: 80, pattern: '^https?://[^\\s]+$' } } })
})

it('clears the previous rules on every drawer type change instead of restoring hidden constraints', async () => {
  const user = userEvent.setup(), apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="type" initialField={{ ...field, validation: { minLength: 2, pattern: '^a$' } }} onApply={apply} onOpenChange={vi.fn()} />)
  await user.click(screen.getByLabelText('类型')); await user.click(screen.getByRole('option', { name: '数字' }))
  await user.click(screen.getByLabelText('类型')); await user.click(screen.getByRole('option', { name: '文本' }))
  await user.click(screen.getByRole('button', { name: '应用到草稿' }))
  expect(apply).toHaveBeenCalledWith({ definition: { key: 'email', name: '邮箱', type: 'string', required: false, validation: {} } })
})

it('shows invalid scalar default errors at their control without an unhandled rejection', async () => {
  const apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="bad-number" initialDefinition={{ key: 'amount', name: '金额', type: 'number', required: false, validation: {} }} existingRecordDefault={0} hasDefault onApply={apply} onOpenChange={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('现有记录默认值'), { target: { value: 'abc' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  expect(await screen.findByText('请输入有效数字')).toBeVisible()
  expect(screen.getByLabelText('现有记录默认值')).toHaveFocus()
  expect(screen.getByLabelText('现有记录默认值')).toHaveAttribute('aria-invalid', 'true')
  expect(apply).not.toHaveBeenCalled()
})

it('focuses an invalid date offset rather than the unrelated field definition', async () => {
  const apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="bad-offset" initialDefinition={{ key: 'date', name: '日期', type: 'date', required: false, validation: {} }} existingRecordDefault={{ kind: 'date', precision: 'datetime', value: '2026-09-14T10:00:00', offset: 'Z' }} hasDefault onApply={apply} onOpenChange={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('现有记录默认值时区偏移'), { target: { value: '+99:00' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  expect(await screen.findByText('请输入有效时区偏移')).toBeVisible()
  expect(screen.getByLabelText('现有记录默认值时区偏移')).toHaveFocus()
  expect(apply).not.toHaveBeenCalled()
})

it.each(['readonly', 'closed', 'session', 'epoch', 'unmount'])('does not apply after %s changes during async validation', async change => {
  const apply = vi.fn(), p = { open: true, sessionKey: 'A', initialField: field, onApply: apply, onOpenChange: vi.fn() }
  const view = render(<SchemaFieldDrawer {...p} />)
  fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: '旧草稿' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  if (change === 'unmount') view.unmount()
  else view.rerender(<SchemaFieldDrawer {...p} readonly={change === 'readonly'} open={change !== 'closed'} sessionKey={change === 'session' ? 'B' : 'A'} submissionEpoch={change === 'epoch' ? 2 : 0} />)
  await act(async () => {})
  expect(apply).not.toHaveBeenCalled()
})

it('rejects a restored draft that changes a protected existing key', async () => {
  const apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="bad-key" initialField={field} initialDefinition={{ ...field, key: 'other' }} onApply={apply} onOpenChange={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: '修改' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  expect(await screen.findByText('已有字段的字段键不可修改。')).toBeVisible()
  expect(apply).not.toHaveBeenCalled()
})

it('does not label a saved custom pattern as a URL preset even when its text matches', () => {
  render(<SchemaFieldDrawer open sessionKey="saved-pattern" initialField={{ ...field, validation: { pattern: '^https?://[^\\s]+$' } }} onApply={vi.fn()} onOpenChange={vi.fn()} />)
  expect(screen.getByLabelText('校验规则')).toHaveTextContent('自定义规则')
  expect(screen.getByLabelText('Python 正则表达式')).toHaveValue('^https?://[^\\s]+$')
})

it.each([{ type: 'number' as const, value: 0 }, { type: 'boolean' as const, value: false }, { type: 'string' as const, value: '' }])('retains the typed $type default without coercing empty, false or zero', async ({ type, value }) => {
  const apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey={`typed-${type}`} initialDefinition={{ key: 'typed', name: '原名', type, required: false, validation: {} }} existingRecordDefault={value} hasDefault onApply={apply} onOpenChange={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: '修改后' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  await waitFor(() => expect(apply).toHaveBeenCalledWith({ definition: { key: 'typed', name: '修改后', type, required: false, validation: {} }, existingRecordDefault: value }))
})

it('rejects a restored draft that changes the identity type', async () => {
  const apply = vi.fn()
  render(<SchemaFieldDrawer open sessionKey="bad-identity" initialField={field} isIdentityField initialDefinition={{ ...field, type: 'number' }} onApply={apply} onOpenChange={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('显示名称'), { target: { value: '修改' } })
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  expect(await screen.findByRole('alert')).toHaveTextContent('身份字段的类型不可修改。')
  expect(screen.getByLabelText('类型')).toHaveFocus()
  expect(apply).not.toHaveBeenCalled()
})
