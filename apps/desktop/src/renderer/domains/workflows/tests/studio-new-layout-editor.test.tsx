import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../components/Toolbar', () => ({ Toolbar: () => <div data-testid="toolbar" /> }))
vi.mock('../components/ModuleSidebar', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../components/ModuleSidebar')>()),
  ModuleSidebar: () => <div data-testid="sidebar" />,
}))
vi.mock('../components/ConfigPanel', () => ({ ConfigPanel: () => <aside data-testid="config-panel" /> }))
vi.mock('../components/LogPanel', () => ({ LogPanel: () => <div data-testid="log-panel" /> }))
vi.mock('../components/BlockFlowView', () => ({ BlockFlowView: () => <div /> }))
vi.mock('@xyflow/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@xyflow/react')>()
  return {
    ...actual,
    ReactFlow: ({ children }: { children?: React.ReactNode }) => <div data-testid="flow">{children}</div>,
    MiniMap: () => <div data-testid="minimap" />,
    Controls: () => null,
    Background: () => null,
  }
})

import { WorkflowEditor } from '../components/WorkflowEditor'
import { useWorkflowStore } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { clearFlag, setFlag } from '../lib/featureFlags'

beforeEach(() => {
  localStorage.clear()
  useGlobalConfigStore.getState().resetConfig()
  useWorkflowStore.setState({ selectedNodeId: null })
})
afterEach(() => { cleanup(); clearFlag('newStudioLayout') })

describe('WorkflowEditor 新布局右栏', () => {
  it('开关开：未选中节点不渲染右栏，选中后渲染', () => {
    setFlag('newStudioLayout', true)
    render(<WorkflowEditor />)
    expect(screen.queryByTestId('config-panel')).toBeNull()
    act(() => useWorkflowStore.setState({ selectedNodeId: 'n1' }))
    expect(screen.getByTestId('config-panel')).toBeTruthy()
    act(() => useWorkflowStore.setState({ selectedNodeId: null }))
    expect(screen.queryByTestId('config-panel')).toBeNull()
  })

  it('开关关：未选中节点也渲染右栏（旧行为）', () => {
    render(<WorkflowEditor />)
    expect(screen.getByTestId('config-panel')).toBeTruthy()
  })
})

describe('WorkflowEditor 小地图默认', () => {
  it('开关开且用户从未设置：不渲染小地图', () => {
    setFlag('newStudioLayout', true)
    render(<WorkflowEditor />)
    expect(screen.queryByTestId('minimap')).toBeNull()
  })

  it('开关开且用户显式打开：渲染小地图', () => {
    setFlag('newStudioLayout', true)
    const s = useGlobalConfigStore.getState()
    s.updateSystemConfig({ canvasWidgets: { ...s.config.system.canvasWidgets, minimap: false } })
    s.updateSystemConfig({ canvasWidgets: { ...useGlobalConfigStore.getState().config.system.canvasWidgets, minimap: true } })
    render(<WorkflowEditor />)
    expect(screen.getByTestId('minimap')).toBeTruthy()
  })

  it('开关关：默认仍显示小地图', () => {
    render(<WorkflowEditor />)
    expect(screen.getByTestId('minimap')).toBeTruthy()
  })
})
