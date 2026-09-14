import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { apiRequest } from '../api'
import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'
let restore = () => {}
afterEach(() => { cleanup(); restore() })
it('security settings explain host ownership without nonfunctional legacy token controls', async () => {
  restore = configureStudioConnection('http://security.fixture', mockRequest)
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: '安全' }))
  expect(await screen.findByText(/访问鉴权由 AutoFlow 宿主统一管理/)).toBeTruthy()
  expect(screen.queryByRole('switch')).toBeNull()
  expect(screen.queryByText(/后端默认监听局域网/)).toBeNull()
  expect(screen.queryByText(/重新生成/)).toBeNull()
  expect(screen.queryByText(/保存令牌/)).toBeNull()
})
it('opening host-owned security settings does not query an obsolete token service', async () => {
  const fetcher = vi.fn(mockRequest)
  restore = configureStudioConnection('http://security.fixture', fetcher)
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: '安全' }))
  await Promise.resolve()
  expect(fetcher.mock.calls.some(([input]) => String(input).includes('/security/'))).toBe(false)
})
it.each([['status','GET'],['toggle','POST'],['regenerate','POST']])('obsolete %s operation reports retired instead of false security state', async (route, method) => {
  const result = await mockRequest(`http://autoflow-studio.mock/api/security/${route}`, { method })
  expect(result.status).toBe(410)
  expect(await result.json()).toMatchObject({ success: false })
})
it('the request wrapper preserves configured headers without adding a legacy WebRPA token', async () => {
  const fetcher = vi.fn<typeof fetch>(async () => Response.json({ success: true }))
  restore = configureStudioConnection('http://security.fixture', fetcher)
  await apiRequest('/fixture', { headers: { Authorization: 'Bearer fixture-only' } })
  const headers = new Headers(fetcher.mock.calls[0][1]?.headers)
  expect(headers.get('Authorization')).toBe('Bearer fixture-only')
  expect(headers.has('X-WebRPA-Token')).toBe(false)
})
