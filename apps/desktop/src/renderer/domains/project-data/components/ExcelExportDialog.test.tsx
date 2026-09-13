import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { ExcelExportDialog } from './ExcelExportDialog'

const fields = [{ key: 'name', name: '姓名', type: 'string', required: false, validation: {}, ref: { fieldId: 'f1' }, writable: true, formula: false, fieldRevision: 1 }, { key: 'age', name: '年龄', type: 'number', required: false, validation: {}, ref: { fieldId: 'f2' }, writable: true, formula: false, fieldRevision: 1 }]
const statuses = [{ statusId: 's1', name: '待办', color: '#fff', order: 1, statusRevision: 1 }]
afterEach(cleanup)
choiceTestEnvironment()

it('emits the reviewed scope, selected columns and status choice', async () => {
  const choose = vi.fn()
  render(<ExcelExportDialog open fields={fields as never} statuses={statuses as never} scope="all" selectedFieldIds={['f1']} includeStatus onScopeChange={vi.fn()} onSelectedFieldIdsChange={vi.fn()} onIncludeStatusChange={vi.fn()} onClose={vi.fn()} onChooseOutput={choose} />)
  await userEvent.click(screen.getByRole('button', { name: '选择保存位置' }))
  expect(choose).toHaveBeenCalledWith({ scope: 'all', fieldIds: ['f1'], includeStatus: true })
})

it('blocks export without columns and exposes current-filter scope', async () => {
  const scope = vi.fn()
  render(<ExcelExportDialog open fields={fields as never} statuses={statuses as never} scope="all" selectedFieldIds={[]} includeStatus={false} onScopeChange={scope} onSelectedFieldIdsChange={vi.fn()} onIncludeStatusChange={vi.fn()} onClose={vi.fn()} onChooseOutput={vi.fn()} />)
  expect(screen.getByRole('alert').textContent).toContain('至少选择一列')
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '导出范围' }), 'filter')
  expect(scope).toHaveBeenCalledWith('filter')
})
