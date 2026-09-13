import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

afterEach(() => { cleanup(); setStudioTransport(mockRequest) })
it('keeps entered credential fields when an HTTP 200 response rejects saving', async () => {
  let saves = 0
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/credentials') && init?.method === 'POST') {
      saves++
      return Response.json({ success: false, error: '测试存储不可写' })
    }
    return mockRequest(input, init)
  })
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: '凭据库' }))
  fireEvent.click(await screen.findByRole('button', { name: '新增凭据' }))
  fireEvent.change(screen.getByPlaceholderText('如：我的邮箱'), { target: { value: 'fixture_credential' } })
  fireEvent.change(screen.getByPlaceholderText('值'), { target: { value: 'dummy-test-value' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(saves).toBe(1))
  expect(await screen.findByText('保存失败：测试存储不可写')).toBeTruthy()
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('value', 'fixture_credential')
  expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-test-value')
})
