import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { choiceTestEnvironment, chooseOption, choiceValue } from '../../testing/choice-user'
import { Modal } from '../Modal'
import { Select } from './select'

choiceTestEnvironment()
afterEach(cleanup)
const options = [{ value: 'active', label: '活动项目' }, { value: 'archived', label: '已归档' }]

it('selects with keyboard and keeps the visible label and submitted value separate', async () => {
  function Example() {
    const [value, setValue] = useState<string | null>('active')
    return <form data-testid="form"><Select aria-label="项目状态" name="status" value={value} onValueChange={setValue} options={options} clearable={false} /></form>
  }
  render(<Example />)
  const control = screen.getByRole('combobox', { name: '项目状态' })
  await chooseOption(userEvent.setup(), control, 'archived')
  expect(choiceValue(control)).toBe('archived')
  expect(new FormData(screen.getByTestId('form') as HTMLFormElement).get('status')).toBe('archived')
  expect(control.tagName).toBe('BUTTON')
  expect(document.querySelector('select:not([aria-hidden="true"])')).toBeNull()
})

it('closes the owned popup before the parent modal when Escape is pressed', async () => {
  const user = userEvent.setup()
  function Example() {
    const [open, setOpen] = useState(true)
    return <Modal open={open} onOpenChange={setOpen} title="项目筛选"><Select aria-label="项目状态" value="active" onValueChange={() => undefined} options={options} clearable={false} /></Modal>
  }
  render(<Example />)
  screen.getByRole('combobox').focus()
  await user.keyboard('{ArrowDown}')
  expect(screen.getByRole('listbox')).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  expect(screen.getByRole('dialog', { name: '项目筛选' })).toBeInTheDocument()
  expect(screen.getByRole('combobox')).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('retains an unavailable selection and does not allow read-only changes', async () => {
  const change = vi.fn()
  render(<Select aria-label="项目状态" value="removed" onValueChange={change} options={options} readOnly />)
  const control = screen.getByRole('combobox')
  control.focus()
  await userEvent.setup().keyboard('{ArrowDown}{Enter}')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(choiceValue(control)).toBe('removed')
  expect(screen.getByText('当前选项不可用，请重新选择')).toBeInTheDocument()
  expect(change).not.toHaveBeenCalled()
})

it('honours a fieldset disabled after its portal was already opened', async () => {
  const change = vi.fn(), user = userEvent.setup()
  const fixture = (disabled: boolean) => <fieldset disabled={disabled}><Select aria-label="项目状态" value="active" options={options} onValueChange={change} clearable={false} /></fieldset>
  const view = render(fixture(false))
  screen.getByRole('combobox').focus()
  await user.keyboard('{ArrowDown}')
  view.rerender(fixture(true))
  await user.click(screen.getByRole('option', { name: '已归档' }))
  expect(change).not.toHaveBeenCalled()
})
