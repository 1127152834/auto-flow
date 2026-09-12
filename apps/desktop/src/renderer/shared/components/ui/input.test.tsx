import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { Input } from './input'
import { Textarea } from './textarea'
afterEach(cleanup)
it('passes input ref and events without coercing numeric drafts', async () => {
  const ref = createRef<HTMLInputElement>(), change = vi.fn()
  render(<Input ref={ref} aria-label="尺寸草稿" inputMode="numeric" defaultValue="" onChange={e => change(e.target.value)} size="sm" />)
  const input = screen.getByRole('textbox', { name: '尺寸草稿' })
  expect(ref.current).toBe(input)
  await userEvent.type(input, '001')
  expect(change).toHaveBeenLastCalledWith('001')
  expect(input).not.toHaveAttribute('size')
})
it('read-only inputs can be focused and selected; disabled inputs cannot be edited', async () => {
  const ref = createRef<HTMLInputElement>()
  render(<><Input ref={ref} aria-label="只读" readOnly value="可复制" /><Input aria-label="禁用" disabled value="保持" /></>)
  ref.current?.focus(); ref.current?.select()
  expect(ref.current).toHaveFocus()
  expect(ref.current?.selectionEnd).toBe(3)
  await userEvent.type(screen.getByRole('textbox', { name: '禁用' }), '变化')
  expect(screen.getByRole('textbox', { name: '禁用' })).toHaveValue('保持')
})
it('textarea forwards ref, multiline changes and a11y attributes', async () => {
  const ref = createRef<HTMLTextAreaElement>(), change = vi.fn()
  render(<Textarea ref={ref} aria-label="描述" aria-invalid aria-describedby="error" onChange={e => change(e.target.value)} />)
  expect(ref.current).toBe(screen.getByRole('textbox', { name: '描述' }))
  await userEvent.type(ref.current!, '一{Enter}二')
  expect(change).toHaveBeenLastCalledWith('一\n二')
  expect(ref.current).toHaveAttribute('aria-describedby', 'error')
})
