import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { ToggleCases } from './ToggleCases'

beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('binds checkbox/switch with RHF, focuses invalid checkbox and resets checked state', async () => {
  const user = userEvent.setup()
  render(<ToggleCases />)
  await user.click(screen.getByRole('button', { name: '提交开关样本' }))
  const consent = screen.getByRole('checkbox', { name: '确认本地样本' })
  expect(consent).toHaveFocus()
  expect(consent).toHaveAttribute('aria-invalid', 'true')
  expect(consent).toHaveAccessibleDescription('请勾选确认项')
  await user.keyboard(' ')
  await user.click(screen.getByRole('switch', { name: '启用样本' }))
  await user.click(screen.getByRole('button', { name: '提交开关样本' }))
  expect(await screen.findByText('开关样本已保存：已确认 / 已启用')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '重置开关样本' }))
  expect(consent).not.toBeChecked()
  expect(screen.getByRole('switch', { name: '启用样本' })).not.toBeChecked()
  expect(consent).not.toHaveAttribute('aria-invalid', 'true')
})
