import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { FormFocusCase } from './FormFocusCase'
beforeEach(() => { vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} }); Element.prototype.scrollIntoView = vi.fn() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('opens the invalid tab before focusing, then tracks selection, blur, clear and reset through RHF', async () => {
  const user = userEvent.setup()
  render(<FormFocusCase />)
  await user.click(screen.getByRole('tab', { name: '验证基础' }))
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '验证保存' }))
  const input = await screen.findByRole('combobox', { name: '验证内核' })
  expect(input).toHaveFocus(); expect(input).toHaveAccessibleDescription('请选择浏览器内核')
  await user.type(input, '#0249')
  await user.click(screen.getByRole('option', { name: 'CloakBrowser 146 · #0249' }))
  await user.tab()
  expect(screen.getByText('字段已访问')).toBeInTheDocument()
  expect(screen.getByText('表单有修改')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '清除选择' }))
  expect(input).toHaveValue('')
  await user.keyboard('{Escape}')
  await user.click(screen.getByRole('button', { name: '重置表单' }))
  expect(screen.getByText('表单未修改')).toBeInTheDocument()
  expect(input).toHaveValue('')
})
