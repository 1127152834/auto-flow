import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { KernelReleaseList, type KernelReleaseItem } from './KernelReleaseList'

afterEach(cleanup)

const release: KernelReleaseItem = {
  edition: 'licensed', version: '151.0.1.1', chromiumVersion: '151.0.1.1', releaseChannel: 'preview',
  publishedAt: null, archive: null, size: null, installed: false,
}

it('locks an uninstalled licensed release and prints unknown nullable fields', () => {
  render(<KernelReleaseList releases={[release]} licensed={false} onDownload={vi.fn()} onCancel={vi.fn()} onRetry={vi.fn()} onSetDefault={vi.fn()} onReveal={vi.fn()} onDelete={vi.fn()} />)
  expect(screen.getByRole('button', { name: '需要 License' })).toBeDisabled()
  expect(screen.getAllByText('未知')).toHaveLength(3)
  expect(screen.getByText('Preview')).toBeInTheDocument()
})
