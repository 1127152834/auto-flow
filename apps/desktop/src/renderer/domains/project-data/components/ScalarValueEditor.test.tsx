import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { scalarDraft } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

afterEach(cleanup)
choiceTestEnvironment()

it('emits every raw intermediate number draft and keeps presence distinct', async () => {
  const change = vi.fn(); const user = userEvent.setup()
  const draft = scalarDraft(12)
  const view = render(<ScalarValueEditor id="amount" label="金额" type="number" draft={draft} onChange={change} allowMissing />)
  await user.clear(screen.getByLabelText('金额'))
  expect(change).toHaveBeenLastCalledWith({ ...draft, text: '' })
  view.rerender(<ScalarValueEditor id="amount" label="金额" type="number" draft={{ ...draft, text: '' }} onChange={change} allowMissing />)
  await chooseOption(user, screen.getByRole('combobox', { name: '金额值状态' }), 'missing')
  expect(change).toHaveBeenLastCalledWith({ ...draft, text: '', presence: 'missing' })
})

it('uses controlled boolean and date controls', async () => {
  const change = vi.fn(); const user = userEvent.setup()
  const draft = { ...scalarDraft(true), presence: 'value' as const }
  const view = render(<ScalarValueEditor id="flag" label="启用" type="boolean" draft={draft} onChange={change} />)
  await chooseOption(user, screen.getByRole('combobox', { name: '启用' }), 'false')
  expect(change).toHaveBeenLastCalledWith({ ...draft, boolean: false })
  view.rerender(<ScalarValueEditor id="when" label="日期" type="date" draft={{ ...draft, precision: 'datetime', text: 'bad', offset: '+0' }} onChange={change} />)
  expect(screen.getByLabelText('日期')).toHaveValue('bad')
  expect(screen.getByLabelText('日期时区偏移')).toHaveValue('+0')
  await user.type(screen.getByLabelText('日期时区偏移'), 'x')
  expect(change).toHaveBeenLastCalledWith({ ...draft, precision: 'datetime', text: 'bad', offset: '+0x' })
})

it('honors disabled and readonly without emitting changes', async () => {
  const change = vi.fn(); const user = userEvent.setup()
  const view = render(<ScalarValueEditor id="value" label="内容" type="string" draft={scalarDraft('draft')} onChange={change} readOnly allowMissing />)
  expect(screen.getByLabelText('内容')).toHaveAttribute('readonly')
  expect(screen.getByRole('combobox', { name: '内容值状态' })).toHaveAttribute('aria-readonly', 'true')
  await user.type(screen.getByLabelText('内容'), 'x'); expect(change).not.toHaveBeenCalled()
  view.rerender(<ScalarValueEditor id="value" label="内容" type="string" draft={scalarDraft('draft')} onChange={change} disabled allowMissing />)
  expect(screen.getByLabelText('内容')).toBeDisabled()
  expect(screen.getByRole('combobox', { name: '内容值状态' })).toBeDisabled()
})

it('identifies missing and date editors by field and displays a non-selectable missing fact', () => {
  const missing = scalarDraft(undefined)
  const { rerender } = render(<>
    <ScalarValueEditor id="first" label="客户编号" type="string" draft={missing} onChange={vi.fn()} />
    <ScalarValueEditor id="second" label="备注" type="string" draft={missing} onChange={vi.fn()} />
  </>)
  expect(screen.getByRole('group', { name: '客户编号' })).toBeVisible()
  expect(screen.getByRole('group', { name: '备注' })).toBeVisible()
  const firstPresence = screen.getByRole('combobox', { name: '客户编号值状态' })
  expect(firstPresence).toHaveAttribute('data-choice-value', 'missing')
  expect(screen.queryByText('当前选项不可用，请重新选择')).not.toBeInTheDocument()

  rerender(<ScalarValueEditor id="when" label="预约时间" type="date" draft={{ ...missing, presence: 'value', precision: 'datetime' }} onChange={vi.fn()} />)
  expect(screen.getByRole('combobox', { name: '预约时间值状态' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: '预约时间精度' })).toBeVisible()
  expect(screen.getByLabelText('预约时间时区偏移')).toBeVisible()
})

it('connects every visible label to its real control', async () => {
  const user = userEvent.setup(); const draft = scalarDraft('text')
  const view = render(<ScalarValueEditor id="note" label="备注内容" type="string" draft={draft} onChange={vi.fn()} />)
  await user.click(screen.getByText('备注内容', { selector: 'label' }))
  expect(screen.getByLabelText('备注内容')).toHaveFocus()

  view.rerender(<ScalarValueEditor id="date" label="执行日期" type="date" draft={{ ...draft, precision: 'datetime', offset: 'Z' }} onChange={vi.fn()} />)
  const precision = screen.getByRole('combobox', { name: '执行日期精度' })
  await user.click(screen.getByText('精度', { selector: 'label' }))
  expect(precision).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('option', { name: '日期时间' })).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(precision).toHaveFocus()
  await user.click(screen.getByText('时区偏移', { selector: 'label' }))
  expect(screen.getByLabelText('执行日期时区偏移')).toHaveFocus()
})
