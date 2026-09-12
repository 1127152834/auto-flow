import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { PasswordInput } from './password-input'
afterEach(cleanup)
it('reveal is opt-in', () => {
  render(<PasswordInput aria-label="密钥" defaultValue="sample" />)
  expect(screen.getByLabelText('密钥')).toHaveAttribute('type', 'password')
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
it('reveal toggles without submitting or changing the input value/ref', async () => {
  const ref = createRef<HTMLInputElement>(), submit = vi.fn(e => e.preventDefault())
  render(<form onSubmit={submit}><PasswordInput ref={ref} aria-label="样本密钥" allowReveal defaultValue="sample-key" /></form>)
  const input = screen.getByLabelText('样本密钥')
  expect(ref.current).toBe(input)
  await userEvent.click(screen.getByRole('button', { name: '显示密码' }))
  expect(input).toHaveAttribute('type', 'text'); expect(input).toHaveValue('sample-key')
  await userEvent.click(screen.getByRole('button', { name: '隐藏密码' }))
  expect(input).toHaveAttribute('type', 'password'); expect(submit).not.toHaveBeenCalled()
})
it('disabled reveal cannot change visibility', async () => {
  render(<PasswordInput aria-label="不可操作" allowReveal disabled defaultValue="sample" />)
  const toggle = screen.getByRole('button', { name: '显示密码' })
  expect(toggle).toBeDisabled(); await userEvent.click(toggle)
  expect(screen.getByLabelText('不可操作')).toHaveAttribute('type', 'password')
})
