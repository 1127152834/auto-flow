import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const storage = vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  return data
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { resolveMinimapVisible, useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

const row = (label: string) => screen.getByText(label, { exact: true }).parentElement as HTMLElement
const toggle = (label: string) => within(row(label)).getByRole('switch')
const visible = () => resolveMinimapVisible(useGlobalConfigStore.getState().config, true)

beforeEach(() => {
  storage.clear()
  storage.set('autoflow.flags.newStudioLayout', 'true')
  useGlobalConfigStore.setState({ config: useGlobalConfigStore.getInitialState().config })
})
afterEach(() => cleanup())

async function openSystemTab() {
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: '系统' }))
  await screen.findByText('画布概览（缩略图）')
}

it('新布局下未设置过的小地图开关显示为关闭，打开一次即生效', async () => {
  await openSystemTab()
  expect(toggle('画布概览（缩略图）').getAttribute('aria-checked')).toBe('false')
  expect(visible()).toBe(false)
  fireEvent.click(toggle('画布概览（缩略图）'))
  expect(visible()).toBe(true)
  expect(useGlobalConfigStore.getState().config.system.minimapExplicit).toBe(true)
})

it('切换其他画布小组件不会把小地图变成显式开启', async () => {
  await openSystemTab()
  fireEvent.click(toggle('模块数量'))
  expect(visible()).toBe(false)
  expect(useGlobalConfigStore.getState().config.system.minimapExplicit).toBe(false)
})
