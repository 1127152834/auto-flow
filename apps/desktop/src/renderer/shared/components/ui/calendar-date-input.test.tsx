import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { choiceTestEnvironment } from '../../testing/choice-user'
import { CalendarDateInput } from './calendar-date-input'
choiceTestEnvironment()
afterEach(cleanup)
function Example({ initial = '2026-09-10' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return <CalendarDateInput aria-label="发布日期" value={value} onValueChange={setValue} />
}
it('keeps raw text for validation and never uses a native date panel', async () => {
  const user = userEvent.setup(); render(<Example />)
  const input = screen.getByRole('textbox', { name: '发布日期' })
  await user.clear(input); await user.type(input, '2026-02-31')
  expect(input).toHaveValue('2026-02-31'); expect(input).toHaveAttribute('type', 'text')
})
it('uses calendar keyboard navigation, commits a local date, and restores trigger focus', async () => {
  const user = userEvent.setup(); render(<Example />)
  const trigger = screen.getByRole('button', { name: '选择发布日期' })
  await user.click(trigger)
  await waitFor(() => expect(document.activeElement?.textContent).toBe('10'))
  await user.keyboard('{ArrowRight}{Enter}')
  expect(screen.getByRole('textbox')).toHaveValue('2026-09-11')
  await waitFor(() => expect(trigger).toHaveFocus())
  await user.click(trigger); await user.keyboard('{Escape}')
  expect(screen.getByRole('textbox')).toHaveValue('2026-09-11')
})
it('does not change an early-year date on open or escape', async () => {
  const user = userEvent.setup(); render(<Example initial="0001-01-05" />)
  await user.click(screen.getByRole('button')); await user.keyboard('{Escape}')
  expect(screen.getByRole('textbox')).toHaveValue('0001-01-05')
})
it('prevents calendar and input edits when readonly', () => {
  const change = vi.fn(); render(<CalendarDateInput aria-label="日期" value="2026-09-10" onValueChange={change} readOnly />)
  expect(screen.getByRole('textbox')).toHaveAttribute('readonly')
  expect(screen.getByRole('button')).toBeDisabled(); expect(change).not.toHaveBeenCalled()
})
it('closes a revoked calendar and does not reopen it when the form unlocks', async () => {
  const user = userEvent.setup(), props = { value: '2026-09-10', onValueChange: vi.fn() }
  const view = render(<CalendarDateInput {...props} />)
  await user.click(screen.getByRole('button')); expect(screen.getByRole('dialog')).toBeVisible()
  view.rerender(<CalendarDateInput {...props} disabled />)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  view.rerender(<CalendarDateInput {...props} />)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
