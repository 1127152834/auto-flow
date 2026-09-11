import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import type { ProfileRead } from '../../../shared/api/types'
import { ProfileList } from './ProfileList'

const profile: ProfileRead = {
  id: 'profile-1', name: '工作环境', description: '长期登录', startUrl: 'about:blank',
  locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: true,
  humanPreset: 'careful', userAgent: null, viewportJson: { width: 1280, height: 800 }, colorScheme: null,
  extensionPathsJson: [], expertArgsJson: [], browserVersion: '145.0.1.1', browserEdition: 'public',
  releaseChannel: 'stable', proxyMode: 'pool', proxyId: null, proxyPoolId: 'pool-1', fingerprintSeed: 12345,
  createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z',
}

afterEach(cleanup)

it('shows the original profile fields and routes every action', async () => {
  const actions = { onEdit: vi.fn(), onDuplicate: vi.fn(), onRegenerate: vi.fn(), onDelete: vi.fn() }
  const user = userEvent.setup()
  render(<ProfileList profiles={[profile]} {...actions} />)
  const item = screen.getByRole('listitem')
  expect(item).toHaveTextContent('工作环境')
  expect(item).toHaveTextContent('长期登录')
  expect(item).toHaveTextContent('12345')
  expect(item).toHaveTextContent('145.0.1.1')
  expect(item).toHaveTextContent('zh-CN / Asia/Shanghai')
  expect(item).toHaveTextContent('代理池')
  for (const [name, callback] of [
    ['编辑 工作环境', actions.onEdit], ['复制 工作环境', actions.onDuplicate],
    ['重新生成 工作环境 的指纹', actions.onRegenerate], ['删除 工作环境', actions.onDelete],
  ] as const) {
    await user.click(within(item).getByRole('button', { name }))
    expect(callback).toHaveBeenCalledWith(profile)
  }
})

it('blocks writes and exposes the active fingerprint state while disabled', () => {
  render(<ProfileList profiles={[profile]} disabled regeneratingId={profile.id} onEdit={vi.fn()} onDuplicate={vi.fn()} onRegenerate={vi.fn()} onDelete={vi.fn()} />)
  expect(screen.getAllByRole('button')).toHaveLength(4)
  expect(screen.getAllByRole('button').every((button) => button.hasAttribute('disabled'))).toBe(true)
  expect(screen.getByText('生成中…')).toBeInTheDocument()
})
