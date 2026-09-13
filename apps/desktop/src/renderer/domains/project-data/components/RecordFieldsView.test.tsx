import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { RecordFieldsView } from './RecordFieldsView'
type S = components['schemas']
afterEach(cleanup)
const field = (id: string): S['DataFieldView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: id }, key: id, name: id, type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
const row = (values: S['DataCellView'][]): S['DataRecordView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '001' } }, values, recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' })
const cell = (fieldId: string, value: S['DataCellView']['value'], readable = true): S['DataCellView'] => ({ fieldId, value, readable, source: 'local' })
it('distinguishes missing, null, empty, zero, false and unreadable evidence', () => {
  render(<RecordFieldsView fields={['missing', 'null', 'empty', 'zero', 'false', 'private'].map(field)} record={row([cell('null', null), cell('empty', ''), cell('zero', 0), cell('false', false), cell('private', 'secret', false)])} />)
  for (const text of ['文本 · 001', '未填写', '空值', '空字符串', '0', '否', '不可读取']) expect(screen.getByText(text)).toBeVisible()
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
