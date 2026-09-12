import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { UiLabPage } from './UiLabPage'

afterEach(cleanup)
it('exposes the validation cases without loading a business API', async () => {
  const user = userEvent.setup()
  render(<UiLabPage />)
  expect(screen.getByRole('heading', { name: 'AutoFlow 控件实验室' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '颜色与密度' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '展开 验证内核' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '打开嵌套验证' }))
  expect(screen.getByRole('dialog', { name: '浏览器配置 · 验证' })).toBeInTheDocument()
})
it('RHF submits an empty choice as an error and focuses the real combobox input', async () => {
  const user = userEvent.setup()
  render(<UiLabPage />)
  await user.click(screen.getByRole('button', { name: '验证保存' }))
  const error = await screen.findByRole('alert')
  expect(error).toHaveTextContent('请选择浏览器内核')
  expect(error.id).not.toBe('')
  expect(screen.getByRole('combobox', { name: '验证内核' }).getAttribute('aria-describedby')).toContain(error.id)
  expect(screen.getByRole('combobox', { name: '验证内核' })).toHaveFocus()
  expect(screen.getByRole('combobox', { name: '验证内核' })).toHaveAttribute('aria-invalid', 'true')
  await user.click(screen.getByRole('button', { name: '重置表单' }))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
