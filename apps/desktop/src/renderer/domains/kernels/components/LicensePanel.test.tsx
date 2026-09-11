import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { LicensePanel } from './LicensePanel'

const createTestQueryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
const renderPanel = (node: ReactNode) => render(<QueryClientProvider client={createTestQueryClient()}>{node}</QueryClientProvider>)

afterEach(cleanup)

it('only offers disconnect when licensed', () => {
  renderPanel(<LicensePanel status={{ configured: true, valid: true, plan: 'pro', expires: null, seats: null }} busy={false} onConnect={vi.fn()} onDisconnect={vi.fn()} />)
  expect(screen.getByRole('button', { name: '退出登录' })).toBeEnabled()
  expect(screen.queryByRole('button', { name: '验证并登录' })).not.toBeInTheDocument()
  expect(screen.getByText(/到期时间 未知/)).toBeInTheDocument()
})

it('submits a trimmed key and keeps failed credentials available for retry', async () => {
  const user = userEvent.setup()
  const onConnect = vi.fn().mockRejectedValue(new Error('License 验证失败'))
  renderPanel(<LicensePanel status={{ configured: false, valid: false, plan: null, expires: null, seats: null }} busy={false} error="License 验证失败" onConnect={onConnect} onDisconnect={vi.fn()} />)
  const input = screen.getByLabelText('License Key')
  await user.type(input, '  secret  ')
  await user.click(screen.getByRole('button', { name: '验证并登录' }))
  expect(onConnect).toHaveBeenCalledWith('secret')
  expect(input).toHaveValue('  secret  ')
  expect(screen.getByRole('alert')).toHaveTextContent('License 验证失败')
})
