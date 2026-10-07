import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { credentialApi } from '../api'
import { ModuleSidebar } from '../components/ModuleSidebar'
import { useLayoutStore } from '../hooks/stores/layoutStore'
import { clearFlag, setFlag } from '../lib/featureFlags'

beforeEach(() => {
  localStorage.clear()
  useLayoutStore.getState().resetLayout()
  vi.spyOn(credentialApi, 'list').mockResolvedValue({ success: true, data: { success: true, credentials: [] } } as never)
})
afterEach(() => { cleanup(); clearFlag('newStudioLayout'); vi.restoreAllMocks() })

describe('ModuleSidebar 数据标签页', () => {
  it('与内置、自定义并列，切换后显示数据侧栏，切回内置显示模块搜索', () => {
    render(<ModuleSidebar />)
    expect(screen.getByRole('button', { name: '内置' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '自定义' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '数据' }))
    expect(screen.getByRole('heading', { name: '输入字段' })).toBeTruthy()
    expect(screen.queryByPlaceholderText('搜索模块/拼音/英文...')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '内置' }))
    expect(screen.getByPlaceholderText('搜索模块/拼音/英文...')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: '输入字段' })).toBeNull()
  })

  it('三个标签的文字不换行（256px 栏宽实测曾把"自定义"挤成两行）', () => {
    render(<ModuleSidebar />)
    for (const name of ['内置', '自定义', '数据']) expect(screen.getByRole('button', { name }).className).toContain('whitespace-nowrap')
  })

  it('折叠再展开后停留在数据标签页，折叠记忆不回归', () => {
    setFlag('newStudioLayout', true)
    render(<ModuleSidebar />)
    fireEvent.click(screen.getByRole('button', { name: '数据' }))
    fireEvent.click(screen.getByRole('button', { name: '收起模块列表' }))
    expect(useLayoutStore.getState().leftCollapsed).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '展开模块列表' }))
    expect(useLayoutStore.getState().leftCollapsed).toBe(false)
    expect(screen.getByRole('heading', { name: '输入字段' })).toBeTruthy()
  })
})
