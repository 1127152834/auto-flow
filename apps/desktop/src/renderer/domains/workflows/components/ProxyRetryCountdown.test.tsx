import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ProxyRetryCountdown } from './ProxyRetryCountdown'
afterEach(() => { cleanup(); vi.useRealTimers() })
test('counts down the configured wait and disappears on stop or expiry', () => {
  vi.useFakeTimers(); vi.setSystemTime(1000)
  const view = render(<ProxyRetryCountdown retryAt={11000} active />)
  expect(screen.getByLabelText('代理重试倒计时').textContent).toContain('10 秒')
  act(() => vi.advanceTimersByTime(3000))
  expect(screen.getByLabelText('代理重试倒计时').textContent).toContain('7 秒')
  view.rerender(<ProxyRetryCountdown retryAt={11000} active={false} />)
  expect(screen.queryByLabelText('代理重试倒计时')).toBeNull()
  view.rerender(<ProxyRetryCountdown retryAt={null} active />)
  expect(screen.queryByLabelText('代理重试倒计时')).toBeNull()
})
