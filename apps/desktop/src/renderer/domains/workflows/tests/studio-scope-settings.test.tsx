import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
})

import { GlobalConfigDialog } from '../components/GlobalConfigDialog'

afterEach(cleanup)

it('does not expose database or browser-engine management in Studio global settings', () => {
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)

  expect(screen.queryByRole('button', { name: '数据库' })).toBeNull()
  expect(screen.queryByRole('button', { name: '浏览器' })).toBeNull()
  expect(screen.queryByText('浏览器类型')).toBeNull()
  expect(screen.queryByText('Microsoft Edge')).toBeNull()
  expect(screen.queryByText('Google Chrome')).toBeNull()
})
