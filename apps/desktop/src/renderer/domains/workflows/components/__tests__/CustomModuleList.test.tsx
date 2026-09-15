// Source: WebRPA@5ccb900e, components/workflow/__tests__/CustomModuleList.test.tsx; see SOURCE.md for license and adaptation boundaries.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { CustomModuleList } from '../CustomModuleList'
import { useCustomModuleStore } from '../../hooks/stores/customModuleStore'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: Root
const originalDeleteModule = useCustomModuleStore.getState().deleteModule
const originalUpdateModule = useCustomModuleStore.getState().updateModule

function makeModule(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    name: id,
    display_name: id,
    description: '',
    category: '',
    parameters: [],
    outputs: [],
    usage_count: 0,
    is_favorite: false,
    sort_order: 0,
    created_at: new Date().toISOString(),
    icon: '',
    color: '#8B5CF6',
    tags: [],
    workflow: { nodes: [], edges: [] },
    ...extra,
  }
}

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  useCustomModuleStore.setState({
    modules: [], isLoading: false, error: null,
    deleteModule: originalDeleteModule,
    updateModule: originalUpdateModule,
  })
})

afterEach(() => {
  act(() => { root.unmount() })
  container.remove()
  // 清理可能残留的弹窗 portal
  document.body.querySelectorAll('[role="dialog"]').forEach((n) => n.remove())
})

const noop = () => {}

describe('CustomModuleList 渲染与交互', () => {
  it('渲染模块列表项（显示名）', () => {
    useCustomModuleStore.setState({ modules: [makeModule('mod_alpha', { display_name: '登录模块' }) as any] })
    act(() => {
      root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />)
    })
    expect(container.textContent).toContain('登录模块')
  })

  it('无模块时显示空状态', () => {
    act(() => {
      root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />)
    })
    expect(container.textContent).toContain('还没有自定义模块')
  })

  it('点击删除弹出自定义确认弹窗（非浏览器原生 confirm）', () => {
    useCustomModuleStore.setState({ modules: [makeModule('mod_del', { display_name: '待删模块' }) as any] })
    // 确保不会误触发原生 confirm
    const nativeConfirm = vi.spyOn(window, 'confirm')
    act(() => {
      root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />)
    })
    const delBtn = Array.from(container.querySelectorAll('button')).find((b) => b.title === '删除')
    expect(delBtn).toBeDefined()
    act(() => { delBtn!.dispatchEvent(new MouseEvent('click', { bubbles: true })) })
    // 自定义确认弹窗（role=dialog/alertdialog）出现，并含删除提示文案
    const dlg = document.body.querySelector('[role="dialog"], [role="alertdialog"]')
    expect(dlg).not.toBeNull()
    expect(document.body.textContent).toContain('删除自定义模块')
    // 没有使用浏览器原生 confirm
    expect(nativeConfirm).not.toHaveBeenCalled()
    nativeConfirm.mockRestore()
  })

  it('取消删除时保留模块且不发送删除请求', async () => {
    const remove = vi.fn(async () => true)
    useCustomModuleStore.setState({
      modules: [makeModule('mod_keep', { display_name: '保留模块' }) as any],
      deleteModule: remove,
    })
    act(() => { root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />) })
    const delBtn = Array.from(container.querySelectorAll('button')).find((button) => button.title === '删除')!
    act(() => { delBtn.click() })
    const cancel = Array.from(document.body.querySelectorAll('button')).find((button) => button.textContent === '取消')!
    await act(async () => { cancel.click() })
    expect(remove).not.toHaveBeenCalled()
    expect(container.textContent).toContain('保留模块')
  })

  it('删除失败时保留模块并显示服务错误', async () => {
    const remove = vi.fn(async () => {
      useCustomModuleStore.setState({ error: '模块仍被工作流引用，无法删除' })
      return false
    })
    useCustomModuleStore.setState({
      modules: [makeModule('mod_used', { display_name: '被引用模块' }) as any],
      deleteModule: remove,
    })
    act(() => { root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />) })
    const delBtn = Array.from(container.querySelectorAll('button')).find((button) => button.title === '删除')!
    act(() => { delBtn.click() })
    const confirm = Array.from(document.body.querySelectorAll('button')).find((button) => button.textContent === '删除')!
    await act(async () => { confirm.click() })
    expect(remove).toHaveBeenCalledWith('mod_used')
    expect(container.textContent).toContain('被引用模块')
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('模块仍被工作流引用，无法删除')
  })

  it('收藏更新失败时保留原状态并显示服务错误', async () => {
    const update = vi.fn(async () => {
      useCustomModuleStore.setState({ error: '收藏更新失败' })
      return null
    })
    useCustomModuleStore.setState({
      modules: [makeModule('mod_favorite', { display_name: '收藏候选' }) as any],
      updateModule: update,
    })
    act(() => { root.render(<CustomModuleList onCreateNew={noop} onManage={noop} onDragStart={noop} />) })
    const favorite = Array.from(container.querySelectorAll('button')).find((button) => button.title === '收藏')!
    await act(async () => { favorite.click() })
    expect(update).toHaveBeenCalledWith('mod_favorite', { is_favorite: true })
    expect(container.querySelector('button[title="收藏"]')).not.toBeNull()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('收藏更新失败')
  })
})
