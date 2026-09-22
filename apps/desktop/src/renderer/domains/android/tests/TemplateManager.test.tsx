import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import { TemplateManager } from '../components/TemplateManager'
import type { Profile } from '../fleet-api'

afterEach(cleanup)
const original: Profile = { id: '00000000-0000-4000-8000-000000000001', revision: 1, name: '验证模板', imageId: `sha256:${'a'.repeat(64)}`, width: 720, height: 1280, dpi: 320, cpu: 1, memoryMb: 1536, locale: 'zh-CN', timezone: 'Asia/Shanghai', shellRoot: 'unknown', applicationRoot: 'unknown', archived: false }

function setup(initial: Profile[] = [], initialImages = [{ id: 'img-1', imageId: original.imageId, name: '标准镜像', reference: 'local:standard', revision: 1, state: 'verified', verification: { state: 'passed' }, createdAt: '' }]) {
  let records = initial.map(item => ({ ...item }))
  let images = initialImages
  const api = {
    profiles: async () => records.map(item => ({ ...item })),
    images: async () => ({ items: images, total: images.length, nextCursor: null }),
    standardProfile: async () => original,
    archiveProfile: vi.fn(async (id: string, body: { requestId: string; expectedRevision: number }) => {
      const saved = records.find(profile => profile.id === id)
      if (!saved || saved.revision !== body.expectedRevision) throw new ApiClientError('环境配置已更新，请重新加载', 409, 'ANDROID_PROFILE_CONFLICT')
      const next = { ...saved, archived: true, revision: saved.revision + 1 }
      records = records.map(profile => profile.id === id ? next : profile)
      return next
    }),
    saveProfile: async (item: Profile) => {
      const saved = records.find(profile => profile.id === item.id)
      if ((saved?.revision ?? 0) !== item.revision) throw new ApiClientError('环境配置已更新，请重新加载', 409, 'ANDROID_PROFILE_CONFLICT')
      const next = { ...item, revision: item.revision + 1 }
      records = [...records.filter(profile => profile.id !== item.id), next]
      return next
    },
  }
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><TemplateManager api={api} /></QueryClientProvider>)
  return { api, records: () => records, replace: (items: Profile[]) => { records = items }, setImages: (items: typeof images) => { images = items } }
}

it('creates a template with a fixed image and complete configuration', async () => {
  const state = setup()
  await userEvent.click(await screen.findByRole('button', { name: '新建模板' }))
  await userEvent.type(screen.getByLabelText('模板名称'), '中文测试模板')
  await userEvent.type(screen.getByLabelText('固定镜像 ID'), original.imageId)
  await userEvent.click(screen.getByRole('button', { name: '保存模板' }))
  expect(await screen.findByText('中文测试模板')).toBeVisible()
  expect(state.records()).toEqual([expect.objectContaining({ name: '中文测试模板', imageId: original.imageId, revision: 1, width: 720, height: 1280, shellRoot: 'unknown', applicationRoot: 'unknown' })])
})

it('copies configuration into a new identity and requires archive confirmation', async () => {
  const state = setup([original])
  await userEvent.click(await screen.findByRole('button', { name: '复制验证模板' }))
  expect(screen.getByLabelText('模板名称')).toHaveValue('验证模板 副本')
  await userEvent.click(screen.getByRole('button', { name: '保存模板' }))
  await screen.findByText('验证模板 副本')
  expect(state.records()).toHaveLength(2)
  expect(state.records()[1].id).not.toBe(original.id)
  expect(state.records()[1]).toMatchObject({ revision: 1, imageId: original.imageId, archived: false })
  await userEvent.click(screen.getByRole('button', { name: '归档验证模板' }))
  expect(state.records()[0].archived).toBe(false)
  expect(screen.getByText('归档后不能用于新建实例，已创建实例的配置保持不变。')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '确认归档' }))
  expect(state.api.archiveProfile).toHaveBeenCalledWith(original.id, expect.objectContaining({ expectedRevision: original.revision }))
  await waitFor(() => expect(state.records().find(item => item.id === original.id)?.archived).toBe(true))
  expect(screen.queryByRole('button', { name: '编辑验证模板' })).not.toBeInTheDocument()
})

it('blocks stale revision writes until the user reloads the current template', async () => {
  const state = setup([original])
  await userEvent.click(await screen.findByRole('button', { name: '编辑验证模板' }))
  state.replace([{ ...original, revision: 2, memoryMb: 2048 }])
  await userEvent.clear(screen.getByLabelText('模板名称'))
  await userEvent.type(screen.getByLabelText('模板名称'), '旧版本编辑')
  await userEvent.click(screen.getByRole('button', { name: '保存模板' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('模板已更新，请重新加载后编辑')
  expect(screen.getByRole('button', { name: '保存模板' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '重新加载模板' }))
  expect(screen.getByLabelText('模板名称')).toHaveValue(original.name)
  expect(screen.getByLabelText('内存 MB')).toHaveValue(2048)
  expect(screen.getByRole('button', { name: '保存模板' })).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '保存模板' }))
  await waitFor(() => expect(state.records()[0].revision).toBe(3))
})

it('does not allow an empty or unverified image to be saved', async () => {
  setup([], [{ id: 'img-1', imageId: original.imageId, name: '未验证镜像', reference: 'local:unknown', revision: 1, state: 'registered', verification: { state: 'unknown' }, createdAt: '' }])
  await userEvent.click(await screen.findByRole('button', { name: '新建模板' }))
  expect(screen.getByRole('button', { name: '保存模板' })).toBeDisabled()
  await userEvent.type(screen.getByLabelText('模板名称'), '无镜像模板')
  await userEvent.type(screen.getByLabelText('固定镜像 ID'), original.imageId)
  expect(screen.getByRole('button', { name: '保存模板' })).toBeDisabled()
  expect(screen.getByText(/镜像必须来自已验证目录/)).toBeVisible()
})
