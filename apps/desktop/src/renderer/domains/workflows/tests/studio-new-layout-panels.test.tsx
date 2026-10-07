import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { LogPanel } from '../components/LogPanel'
import { ModuleSidebar } from '../components/ModuleSidebar'
import { useWorkflowStore } from '../editor-store'
import { useLayoutStore } from '../hooks/stores/layoutStore'
import { clearFlag, setFlag } from '../lib/featureFlags'
import { RUNNING_BOTTOM_RATIO, STATUS_BAR_HEIGHT } from '../lib/studioLayoutMetrics'

const footer = () => document.querySelector('footer') as HTMLElement

beforeEach(() => {
  localStorage.clear()
  useLayoutStore.getState().resetLayout()
  useWorkflowStore.setState({ executionStatus: 'pending' as never, logs: [] })
})
afterEach(() => { cleanup(); clearFlag('newStudioLayout') })

describe('LogPanel 新布局', () => {
  it('空闲：一行状态条，高度取常量，可点击展开并记忆', () => {
    setFlag('newStudioLayout', true)
    render(<LogPanel />)
    expect(footer().style.height).toBe(`${STATUS_BAR_HEIGHT}px`)
    const btn = screen.getByRole('button', { name: '展开日志面板' })
    expect(btn.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(btn)
    expect(useLayoutStore.getState().bottomMode).toBe('expanded')
    expect(footer().style.height).toBe(`${useLayoutStore.getState().bottomHeight}px`)
  })

  it('状态条显示最近一条日志', () => {
    setFlag('newStudioLayout', true)
    useWorkflowStore.setState({ logs: [{ id: 'l1', timestamp: '2026-10-06T00:00:00Z', level: 'info', message: '已打开页面' } as never] })
    render(<LogPanel />)
    expect(screen.getByText(/已打开页面/)).toBeTruthy()
  })

  it('运行中：展开到窗口高度 30%，结束后回到状态条', () => {
    setFlag('newStudioLayout', true)
    render(<LogPanel />)
    act(() => useWorkflowStore.setState({ executionStatus: 'running' }))
    expect(footer().style.height).toBe(`${RUNNING_BOTTOM_RATIO * 100}vh`)
    act(() => useWorkflowStore.setState({ executionStatus: 'completed' }))
    expect(footer().style.height).toBe(`${STATUS_BAR_HEIGHT}px`)
  })

  it('用户展开后记忆为展开，运行结束不被收回', () => {
    setFlag('newStudioLayout', true)
    useLayoutStore.getState().setBottomMode('expanded')
    render(<LogPanel />)
    expect(footer().style.height).toBe(`${useLayoutStore.getState().bottomHeight}px`)
    act(() => useWorkflowStore.setState({ executionStatus: 'running' }))
    act(() => useWorkflowStore.setState({ executionStatus: 'completed' }))
    expect(footer().style.height).toBe(`${useLayoutStore.getState().bottomHeight}px`)
  })

  it('开关关：保持旧的展开高度，不渲染状态条', () => {
    render(<LogPanel />)
    expect(footer().style.height).toBe(`${useLayoutStore.getState().bottomHeight}px`)
    expect(screen.queryByRole('button', { name: '展开日志面板' })).toBeNull()
  })
})

describe('ModuleSidebar 新布局折叠记忆', () => {
  it('折叠按钮带 aria-expanded，折叠写入 layoutStore，重新挂载后保留', () => {
    setFlag('newStudioLayout', true)
    const { unmount } = render(<ModuleSidebar />)
    const collapse = screen.getByRole('button', { name: '收起模块列表' })
    expect(collapse.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(collapse)
    expect(useLayoutStore.getState().leftCollapsed).toBe(true)
    unmount()
    render(<ModuleSidebar />)
    const expand = screen.getByRole('button', { name: '展开模块列表' })
    expect(expand.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(expand)
    expect(useLayoutStore.getState().leftCollapsed).toBe(false)
  })

  it('开关关：折叠仍是本地状态，不写入 layoutStore', () => {
    render(<ModuleSidebar />)
    fireEvent.click(screen.getByRole('button', { name: '收起模块列表' }))
    expect(useLayoutStore.getState().leftCollapsed).toBe(false)
  })
})
