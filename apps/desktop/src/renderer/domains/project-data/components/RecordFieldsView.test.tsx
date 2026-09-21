import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { RecordFieldsView } from './RecordFieldsView'
type S = components['schemas']
afterEach(cleanup)
const field = (id: string): S['DataFieldView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: id }, key: id, name: id, type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
const row = (values: S['DataCellView'][]): S['DataRecordView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '001' } }, values, validationIssues: [], recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' })
const cell = (fieldId: string, value: S['DataCellView']['value'], readable = true): S['DataCellView'] => ({ fieldId, value, readable, source: 'local' })
it('distinguishes missing, null, empty, zero, false and unreadable evidence', () => {
  render(<RecordFieldsView fields={['missing', 'null', 'empty', 'zero', 'false', 'private'].map(field)} record={row([cell('null', null), cell('empty', ''), cell('zero', 0), cell('false', false), cell('private', 'secret', false)])} />)
  for (const text of ['未填写', '空值', '空字符串', '0', '否', '不可读取']) expect(screen.getByText(text)).toBeVisible()
  expect(screen.queryByText('secret')).not.toBeInTheDocument()
})
it('opens only validated web links through the controlled bridge and shows failures in place', async () => {
  const open = vi.fn().mockResolvedValue({ ok: false, error: { code: 'EXTERNAL_LINK_FAILED', message: '无法打开链接' } })
  render(<RecordFieldsView fields={['网址', 'file', 'credentials'].map(field)} record={row([cell('网址', 'https://example.com/a'), cell('file', 'file:///tmp/x'), cell('credentials', 'https://user:pass@example.com')])} openExternalLink={open} />)
  expect(screen.getAllByRole('button', { name: /打开链接/ })).toHaveLength(1)
  await userEvent.setup().click(screen.getByRole('button', { name: '打开链接 网址' }))
  expect(open).toHaveBeenCalledWith('https://example.com/a')
  expect(await screen.findByRole('alert')).toHaveTextContent('无法打开链接')
})
it('copies the exact original link and keeps date precision and offsets', async () => {
  const user = userEvent.setup(), copy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
  render(<RecordFieldsView fields={['网址', '日期'].map(field)} record={row([cell('网址', 'https://example.com/a?q=%20'), cell('日期', { kind: 'date', precision: 'datetime', value: '2026-09-13T12:00:00.123456789', offset: '+08:00' })])} />)
  await user.click(screen.getByRole('button', { name: '复制链接 网址' }))
  expect(copy).toHaveBeenCalledWith('https://example.com/a?q=%20')
  expect(screen.getByText('2026-09-13T12:00:00.123456789 +08:00')).toBeVisible()
})

it('groups gallery business fields under the title and keeps label/value row separation',()=>{
 render(<RecordFieldsView fields={[field('标题')]} record={row([cell('标题','温室')])}/>);
 expect(screen.getByRole('heading',{name:'业务字段'})).toHaveClass('text-2xl');
 expect(screen.getByText('业务字段只读展示，修改请点击「编辑记录」。')).toBeVisible();
 expect(screen.getByText('标题').parentElement).toHaveClass('sm:grid-cols-[180px_minmax(0,1fr)]');
})
it('shows a field identity once while preserving unrelated fields with the same value',()=>{
 render(<RecordFieldsView identityFieldId="记录编号" fields={[field('记录编号'),field('另一个字段')]} record={row([cell('记录编号','001'),cell('另一个字段','001')])}/>);
 expect(screen.getAllByText('记录编号')).toHaveLength(1);
 expect(screen.getByText('另一个字段')).toBeVisible();
 expect(screen.getAllByText('001')).toHaveLength(2);
})

it('omits a system UUID identity row and gives a stale field a semantic label',()=>{
 const uuid='11111111-2222-4333-8444-555555555555',system={...row([cell('标题','业务标题')]),ref:{...row([]).ref,recordKey:{type:'uuid' as const,value:uuid}}}
 const view=render(<RecordFieldsView fields={[field('标题')]} record={system}/>)
 expect(document.body.textContent).not.toContain(uuid);expect(screen.queryByText('记录身份')).not.toBeInTheDocument()
 view.rerender(<RecordFieldsView identityFieldId="11111111-2222-4333-8444-555555555556" fields={[]} record={system}/>)
 expect(screen.getAllByText('字段已失效')).toHaveLength(2);expect(document.body.textContent).not.toContain(uuid)
})

it('shows structured business validation issues beside the original value', () => { const rowWithIssue = { ...row([cell('amount', 'not-a-number')]), validationIssues: [{ fieldId: 'amount', code: 'INVALID_PROJECT_DATA', rule: 'type', message: 'must be a finite JSON-safe number' }] }; render(<RecordFieldsView fields={[field('amount')]} record={rowWithIssue} />); expect(screen.getByRole('status')).toHaveTextContent('格式不符合字段要求'); expect(screen.getByRole('status')).toHaveTextContent('must be a finite JSON-safe number') })
