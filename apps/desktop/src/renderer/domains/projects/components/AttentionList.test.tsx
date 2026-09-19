import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { AttentionList } from './AttentionList'

afterEach(cleanup)

const batchItem = { kind: 'batch' as const, resource: { type: 'batch' as const, projectId: 'p', batchId: 'b1' }, severity: 'error' as const, message: '批次失败', occurredAt: '2026-09-19T10:00:00Z' }

it('hides the card when nothing needs attention', () => {
  const { container } = render(<AttentionList items={[]} onOpen={vi.fn()} />)
  expect(container).toBeEmptyDOMElement()
})

it('maps severity to the approved visual weight and opens a reachable object', async () => {
  const open = vi.fn()
  render(<AttentionList items={[batchItem]} onOpen={open} />)
  expect(screen.getByRole('listitem')).toHaveClass('border-danger/40')
  await userEvent.click(screen.getByRole('button', { name: '查看' }))
  expect(open).toHaveBeenCalledWith({ tab: 'runs', batchId: 'b1' })
})

it('states that an object without a page cannot be opened instead of faking a link', () => {
  render(<AttentionList items={[{ ...batchItem, resource: { type: 'sync', projectId: 'p', tableId: 't1', syncOperationId: 's1' } }]} onOpen={vi.fn()} />)
  expect(screen.queryByRole('button', { name: '查看' })).not.toBeInTheDocument()
  expect(screen.getByText('暂不可打开')).toHaveAttribute('title', '该对象没有可打开的页面')
})
