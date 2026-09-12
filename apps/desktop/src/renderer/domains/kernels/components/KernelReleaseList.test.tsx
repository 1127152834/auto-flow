import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

it('keeps channel statuses separate but blocks a retry sharing an active install target', async () => {
  const user = userEvent.setup()
  const stable = { ...release, releaseChannel: 'stable' as const }
  const failed = { id: 'stable-op', edition: 'licensed' as const, requestedVersion: release.version, resolvedVersion: null, releaseChannel: 'stable' as const, state: 'failed' as const, progress: null, message: null, error: 'stable failed' }
  const downloading = { ...failed, id: 'preview-op', releaseChannel: 'preview' as const, state: 'downloading' as const, error: null }
  const onCancel = vi.fn()
  const onRetry = vi.fn()
  render(<KernelReleaseList releases={[stable, release]} licensed operations={[failed, downloading]} onDownload={vi.fn()} onCancel={onCancel} onRetry={onRetry} onSetDefault={vi.fn()} onReveal={vi.fn()} onDelete={vi.fn()} />)
  expect(screen.getAllByText(`CloakBrowser ${release.version}`)).toHaveLength(2)
  const stableCard = screen.getByText('Stable').closest('li') as HTMLElement
  const previewCard = screen.getByText('Preview').closest('li') as HTMLElement
  expect(stableCard).toHaveTextContent('stable failed')
  expect(previewCard).toHaveTextContent('下载中')
  expect(within(stableCard).getByRole('button', { name: '重试下载' })).toBeDisabled()
  await user.click(within(previewCard).getByRole('button', { name: '取消下载' }))
  expect(onRetry).not.toHaveBeenCalled()
  expect(onCancel).toHaveBeenCalledWith('preview-op')
})
