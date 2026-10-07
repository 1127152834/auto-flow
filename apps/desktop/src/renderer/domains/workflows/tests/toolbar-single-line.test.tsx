import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { Toolbar } from '../components/Toolbar'
import { useStudioIntegration } from '../hooks/useStudioIntegration'
import { useWorkflowStore } from '../editor-store'
import { useLayoutStore } from '../hooks/stores/layoutStore'
import { useAIAssistantStore } from '../hooks/stores/aiAssistantStore'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { clearFlag, setFlag } from '../lib/featureFlags'
import { TOOLBAR_HEIGHT } from '../lib/studioLayoutMetrics'

function Integration() {
  useStudioIntegration()
  return null
}

const header = () => document.querySelector('header') as HTMLElement
const openMenu = (name: string) => fireEvent.pointerDown(screen.getByRole('button', { name }), { button: 0, ctrlKey: false })
const setAutomation = (on: boolean) => window.history.replaceState({}, '', on ? '/?automationId=a1' : '/')

beforeEach(() => {
  localStorage.clear()
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().markAsSaved()
  useLayoutStore.getState().resetLayout()
  useAIAssistantStore.setState({ isPanelOpen: false })
  useGlobalConfigStore.setState(state => ({
    config: { ...state.config, system: { ...state.config.system, showAIAssistantButton: true, canvasWidgets: { ...state.config.system.canvasWidgets, viewSwitch: true } } },
  }))
})
afterEach(() => { cleanup(); clearFlag('newStudioLayout'); setAutomation(false) })

describe('开关开启：单行工具栏', () => {
  beforeEach(() => setFlag('newStudioLayout', true))

  it('不换行，高度取工具栏常量，且不渲染批量运行', () => {
    render(<Toolbar />)
    expect(header().className).not.toContain('flex-wrap')
    expect(header().style.height).toBe(`${TOOLBAR_HEIGHT}px`)
    expect(screen.queryByText(/批量运行/)).toBeNull()
  })

  it('保存状态用文字表达：已保存 / 未保存 / 运行中', () => {
    render(<Toolbar />)
    expect(screen.getByTestId('save-status').textContent).toBe('已保存')
    act(() => useWorkflowStore.getState().addVariable({ name: 'v', value: '1', type: 'string', scope: 'global' }))
    expect(screen.getByTestId('save-status').textContent).toBe('未保存')
    act(() => useWorkflowStore.getState().setExecutionStatus('running'))
    expect(screen.getByTestId('save-status').textContent).toBe('运行中')
    act(() => useWorkflowStore.getState().setExecutionStatus('stopped'))
  })

  it('撤销/重做随历史启用，点击生效', () => {
    render(<Toolbar />)
    const undo = screen.getByRole('button', { name: '撤销' }) as HTMLButtonElement
    const redo = screen.getByRole('button', { name: '重做' }) as HTMLButtonElement
    expect(undo.disabled).toBe(true)
    expect(redo.disabled).toBe(true)
    act(() => useWorkflowStore.getState().addVariable({ name: 'v', value: '1', type: 'string', scope: 'global' }))
    expect(undo.disabled).toBe(false)
    fireEvent.click(undo)
    expect(useWorkflowStore.getState().variables).toEqual([])
    expect(redo.disabled).toBe(false)
    fireEvent.click(redo)
    expect(useWorkflowStore.getState().variables).toHaveLength(1)
  })

  it('全局配置里关闭"流程图 / 模块条切换"后，工具栏不再显示视图切换', () => {
    useGlobalConfigStore.setState(state => ({
      config: { ...state.config, system: { ...state.config.system, canvasWidgets: { ...state.config.system.canvasWidgets, viewSwitch: false } } },
    }))
    render(<Toolbar />)
    expect(screen.queryByRole('button', { name: '流程图' })).toBeNull()
    expect(screen.queryByRole('button', { name: '模块条' })).toBeNull()
    expect(screen.getByRole('button', { name: '撤销' })).toBeTruthy()
  })

  it('视图切换位于撤销重做之后、试跑之前，并写入布局', () => {
    render(<Toolbar />)
    const before = (a: HTMLElement, b: HTMLElement) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
    const redo = screen.getByRole('button', { name: '重做' })
    const block = screen.getByRole('button', { name: '模块条' })
    const run = screen.getByRole('button', { name: '运行 (F5)' })
    expect(before(redo, block)).toBe(true)
    expect(before(block, run)).toBe(true)
    expect(screen.getByRole('button', { name: '流程图' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(block)
    expect(useLayoutStore.getState().editorViewMode).toBe('block')
    expect(block.getAttribute('aria-pressed')).toBe('true')
  })

  it('试跑菜单含运行、无头运行与三档浏览器追踪', () => {
    render(<Toolbar />)
    const trigger = screen.getByRole('button', { name: '运行 (F5)' })
    expect(trigger.textContent).toContain('试跑')
    openMenu('运行 (F5)')
    expect(screen.getByRole('menuitem', { name: /^运行/ })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: '无头运行' })).toBeTruthy()
    expect(screen.getAllByRole('menuitemradio')).toHaveLength(3)
  })

  it('更多菜单收纳计划任务、自动化浏览器、录制等其余项', () => {
    render(<Toolbar />)
    openMenu('更多操作')
    for (const name of ['计划任务', '自动化浏览器', '网页智能录制', '全局配置', '变量追踪', '教学文档']) {
      expect(screen.getByRole('menuitem', { name: new RegExp(name) })).toBeTruthy()
    }
  })

  it('保留保存/新建/导出等无障碍名称与小助手按钮', () => {
    render(<Toolbar />)
    for (const name of ['新建', '保存', '打开', '导出', '导入整包', 'AI 小助手']) {
      expect(screen.getByRole('button', { name })).toBeTruthy()
    }
    expect(screen.getByRole('button', { name: 'AI 小助手' }).getAttribute('title')).toContain('Ctrl/Cmd+J')
  })
})

describe('命令面板与快捷键', () => {
  it('开关开启：Ctrl/Cmd+K 打开命令面板，不动小助手；Ctrl/Cmd+J 切换小助手', () => {
    setFlag('newStudioLayout', true)
    render(<><Toolbar /><Integration /></>)
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(screen.getByRole('dialog', { name: '命令面板' })).toBeTruthy()
    expect(useAIAssistantStore.getState().isPanelOpen).toBe(false)
    fireEvent.keyDown(window, { key: 'j', metaKey: true })
    expect(useAIAssistantStore.getState().isPanelOpen).toBe(true)
    fireEvent.keyDown(window, { key: 'j', metaKey: true })
    expect(useAIAssistantStore.getState().isPanelOpen).toBe(false)
  })

  it('开关关闭：Ctrl/Cmd+K 仍是小助手，且没有命令面板', () => {
    render(<><Toolbar /><Integration /></>)
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    expect(useAIAssistantStore.getState().isPanelOpen).toBe(true)
    expect(screen.queryByRole('dialog', { name: '命令面板' })).toBeNull()
    expect(screen.queryByRole('button', { name: /命令面板/ })).toBeNull()
  })

  it('入口按钮打开面板；选择撤销命令走同一份历史', () => {
    setFlag('newStudioLayout', true)
    render(<Toolbar />)
    act(() => useWorkflowStore.getState().addVariable({ name: 'v', value: '1', type: 'string', scope: 'global' }))
    fireEvent.click(screen.getByRole('button', { name: /命令面板/ }))
    const dialog = screen.getByRole('dialog', { name: '命令面板' })
    fireEvent.change(within(dialog).getByRole('combobox'), { target: { value: '撤销' } })
    fireEvent.keyDown(within(dialog).getByRole('combobox'), { key: 'Enter' })
    expect(useWorkflowStore.getState().variables).toEqual([])
  })

  it.each([true, false])('自动化模式下命令禁用与按钮一致 (automation=%s)', automation => {
    setFlag('newStudioLayout', true)
    setAutomation(automation)
    render(<Toolbar />)
    fireEvent.click(screen.getByRole('button', { name: /命令面板/ }))
    const optionDisabled = (name: string) => screen.getByRole('option', { name }).getAttribute('aria-disabled') === 'true'
    const buttonDisabled = (name: string) => (screen.getByRole('button', { name, hidden: true }) as HTMLButtonElement).disabled
    for (const name of ['新建', '打开', '导入整包', '保存', '导出']) {
      expect(optionDisabled(name), name).toBe(buttonDisabled(name))
    }
    expect(optionDisabled('新建')).toBe(automation)
  })
})
