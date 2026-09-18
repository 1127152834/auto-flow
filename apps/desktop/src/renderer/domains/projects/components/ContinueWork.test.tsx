import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ContinueWork } from './ContinueWork'

afterEach(cleanup)

const batch = (index: number) => ({ activityId: `a${index}`, kind: 'batch' as const, resource: { type: 'batch' as const, projectId: 'p', batchId: `b${index}` }, summary: `批次 ${index} 未完成`, occurredAt: `2026-09-19T1${index}:00:00Z` })

it('offers real batch entries and never a not-connected placeholder', async () => {
  const open = vi.fn()
  render(<ContinueWork items={[batch(1)]} onOpen={open} />)
  expect(screen.getByRole('region', { name: '继续工作' })).toBeVisible()
  expect(screen.queryByText(/尚未接入/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '继续' }))
  expect(open).toHaveBeenCalledWith({ tab: 'runs', batchId: 'b1' })
})

it('caps the list and hides itself when no recorded entry is reachable', () => {
  const { rerender } = render(<ContinueWork items={[1, 2, 3, 4, 5, 6].map(batch)} onOpen={vi.fn()} />)
  expect(screen.getAllByRole('listitem')).toHaveLength(4)
  rerender(<ContinueWork items={[{ ...batch(1), resource: { type: 'sync', projectId: 'p', tableId: 't1', syncOperationId: 's1' } }]} onOpen={vi.fn()} />)
  expect(screen.queryByRole('region', { name: '继续工作' })).not.toBeInTheDocument()
})
