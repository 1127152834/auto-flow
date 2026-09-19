import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { StatisticsTrend } from './StatisticsTrend'

afterEach(cleanup)

const bucket = (bucketStart: string, succeeded: number, failed: number) => ({
  bucketStart,
  succeeded,
  failed,
  cancelled: 0,
  timed_out: 0,
  interrupted: 0,
})

it('renders only the buckets the server returned and names the gaps instead of inventing empty days', () => {
  render(
    <StatisticsTrend
      buckets={[bucket('2026-09-17T00:00:00Z', 2, 1)]}
      timezone="UTC"
      emptyRangeLabel="9月14日 — 9月19日"
      from="2026-09-14T00:00:00Z"
      to="2026-09-19T00:00:00Z"
      interval="day"
    />,
  )
  expect(screen.getByText('9月17日')).toBeVisible()
  expect(screen.getByText('3 个')).toBeVisible()
  expect(screen.getAllByText(/无已结束任务/)).toHaveLength(2)
})

it('drills into a bucket only when that bucket recorded failures', async () => {
  const drill = vi.fn()
  const props = {
    timezone: 'UTC',
    emptyRangeLabel: '窗口',
    onDrillDown: drill,
    interval: 'day' as const,
  }
  const { rerender } = render(
    <StatisticsTrend buckets={[bucket('2026-09-17T00:00:00Z', 2, 1)]} {...props} />,
  )
  await userEvent.click(screen.getByRole('button', { name: '1' }))
  expect(drill).toHaveBeenCalledWith('failed', '2026-09-17T00:00:00Z')

  rerender(<StatisticsTrend buckets={[bucket('2026-09-17T00:00:00Z', 2, 0)]} {...props} />)
  expect(screen.getByRole('button', { name: '0' })).toBeDisabled()
})

it('states the requested window when no task ended inside it', () => {
  render(<StatisticsTrend buckets={[]} timezone="UTC" emptyRangeLabel="9月14日 — 9月19日" />)
  expect(screen.getByText('9月14日 — 9月19日 无已结束任务。')).toBeVisible()
})
