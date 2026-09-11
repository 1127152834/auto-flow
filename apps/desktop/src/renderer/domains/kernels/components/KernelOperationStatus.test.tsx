import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import type { KernelOperation } from '../../../shared/api/types'
import { KernelOperationStatus } from './KernelOperationStatus'

afterEach(cleanup)

const operation = (progress: number | null): KernelOperation => ({
  id: 'op-1', edition: 'public', requestedVersion: '146.0.1.1', resolvedVersion: null,
  releaseChannel: 'stable', state: 'downloading', progress, message: null, error: null,
})

it('renders unknown progress as indeterminate without inventing a percentage', () => {
  render(<KernelOperationStatus operation={operation(null)} onCancel={vi.fn()} />)
  const progress = screen.getByRole('progressbar', { name: '内核安装进度' })
  expect(progress).not.toHaveAttribute('aria-valuenow')
  expect(progress).toHaveAttribute('aria-valuetext', '进度未知')
  expect(screen.queryByText(/%/)).not.toBeInTheDocument()
})

it('renders the real percentage when the worker supplies one', () => {
  render(<KernelOperationStatus operation={operation(37)} onCancel={vi.fn()} />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '37')
  expect(screen.getByText('37%')).toBeInTheDocument()
})
