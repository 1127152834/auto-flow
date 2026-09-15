import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'
Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)
function mount(type: ModuleType) {
  store.getState().addNode(type, { x: 0, y: 0 })
  render(<ConfigPanel selectedNodeId={store.getState().nodes[0].id} />)
}
function choose(label: string, name: string) {
  fireEvent.keyDown(screen.getByRole('combobox', { name: label }), { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name }))
}
function roundtrip() {
  const document = store.getState().exportWorkflow()
  const expected = store.getState().nodes[0].data
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(document)).toBe(true) })
  expect(store.getState().nodes[0].data).toEqual(expected)
}
it.each(['refresh_page', 'go_back', 'go_forward', 'wait_page_load', 'page_load_complete'] as const)('%s maps each load state through its actual ConfigPanel entry', type => {
  mount(type)
  const field = type === 'page_load_complete' ? 'checkState' : 'waitUntil'
  const label = type === 'page_load_complete' ? '检查状态' : '等待条件'
  expect(screen.getByRole('combobox', { name: label }).textContent).toContain('页面加载完成')
  for (const [value, option] of [['networkidle', '网络空闲'], ['domcontentloaded', 'DOM加载完成'], ['load', '页面加载完成']]) {
    choose(label, option)
    expect(store.getState().nodes[0].data[field]).toBe(value)
  }
  roundtrip()
})
it('switch_tab maps seven modes and both matching selectors while retaining inactive fields', () => {
  mount('switch_tab')
  const values = { tabIndex: 3, tabTitle: '标题 {name}', tabUrl: 'https://test/{path}' }
  act(() => store.getState().updateNodeData(store.getState().nodes[0].id, values))
  for (const [mode, option] of [['index', '按索引切换'], ['title', '按标题切换'], ['url', '按URL切换'], ['next', '切换到下一个'], ['prev', '切换到上一个'], ['first', '切换到第一个'], ['last', '切换到最后一个']]) {
    choose('切换模式', option)
    expect(store.getState().nodes[0].data.switchMode ?? 'index').toBe(mode)
    expect(screen.queryByPlaceholderText('输入标签页标题') !== null).toBe(mode === 'title')
    expect(screen.queryByPlaceholderText('输入标签页URL') !== null).toBe(mode === 'url')
    expect(screen.queryByPlaceholderText('0') !== null).toBe(mode === 'index')
    if (mode === 'title' || mode === 'url') {
      const field = mode === 'title' ? 'tabTitle' : 'tabUrl'
      const text = mode === 'title' ? '新标题 {name}' : 'https://updated.test/{path}'
      const input = screen.getByPlaceholderText(mode === 'title' ? '输入标签页标题' : '输入标签页URL')
      fireEvent.change(input, { target: { value: text } }); fireEvent.blur(input)
      values[field] = text
      expect(store.getState().nodes[0].data[field]).toBe(text)
      for (const [match, name] of [['contains', '包含'], ['startswith', '开头匹配'], ['endswith', '结尾匹配'], ['regex', '正则表达式'], ['exact', '精确匹配']]) {
        choose('匹配模式', name); expect(store.getState().nodes[0].data.matchMode).toBe(match)
      }
    } else expect(screen.queryByRole('combobox', { name: '匹配模式' })).toBeNull()
    expect(store.getState().nodes[0].data).toMatchObject(values)
  }
  for (const [field, placeholder] of [['saveIndexVariable', 'tab_index'], ['saveTitleVariable', 'tab_title'], ['saveUrlVariable', 'tab_url']]) {
    const input = screen.getByPlaceholderText(placeholder)
    fireEvent.change(input, { target: { value: `${placeholder}_结果` } }); fireEvent.blur(input)
    expect(store.getState().nodes[0].data[field]).toBe(`${placeholder}_结果`)
  }
  roundtrip()
})
it('switch_iframe maps all locate modes and preserves inactive targets', () => {
  mount('switch_iframe')
  const values = { iframeIndex: 2, iframeName: 'frame_中文', iframeSelector: 'iframe[data-key="中文"]' }
  act(() => store.getState().updateNodeData(store.getState().nodes[0].id, values))
  for (const [mode, option, placeholder, field, text] of [
    ['index', '索引', '0', 'iframeIndex', '4'],
    ['name', '名称/ID', 'iframe的name或id属性值', 'iframeName', '{框架名}'],
    ['selector', '选择器', "iframe[src*='example.com']", 'iframeSelector', 'iframe[name="{frame}"]'],
  ]) {
    choose('定位方式', option)
    const input = screen.getByPlaceholderText(placeholder)
    fireEvent.change(input, { target: { value: text } }); fireEvent.blur(input)
    expect(store.getState().nodes[0].data[field]).toBe(mode === 'index' ? 4 : text)
    expect(store.getState().nodes[0].data.locateBy ?? 'index').toBe(mode)
  }
  expect(store.getState().nodes[0].data).toMatchObject({ iframeIndex: 4, iframeName: '{框架名}', iframeSelector: 'iframe[name="{frame}"]' })
  roundtrip()
})
it.each(['1abc', '1.5', 'Infinity', '', '{tab}'])('switch_tab index draft %s is not silently truncated', text => {
  mount('switch_tab')
  const input = screen.getByPlaceholderText('0')
  fireEvent.change(input, { target: { value: text } }); fireEvent.blur(input)
  expect(store.getState().nodes[0].data.tabIndex).toBe(text === '1.5' ? 1.5 : text)
})
it('wait_page_load timeout uses the shared numeric editor with its own field and minimum', () => {
  mount('wait_page_load')
  const input = screen.getByLabelText('超时时间（秒）') as HTMLInputElement
  expect(input.value).toBe('60')
  for (const [text, value, invalid] of [['0', 0, true], ['2.5', 2.5, false], ['{seconds}', '{seconds}', false], ['', '', false]] as const) {
    fireEvent.change(input, { target: { value: text } }); fireEvent.blur(input)
    expect(store.getState().nodes[0].data.timeout).toBe(value)
    expect(input.getAttribute('aria-invalid') === 'true').toBe(invalid)
  }
  roundtrip()
})
it('page_load_complete output field edits and restores its declared name', () => {
  mount('page_load_complete')
  const input = screen.getByPlaceholderText('page_loaded') as HTMLInputElement
  expect(input.value).toBe('page_loaded')
  fireEvent.change(input, { target: { value: '页面已加载' } }); fireEvent.blur(input)
  expect(store.getState().nodes[0].data.saveToVariable).toBe('页面已加载')
  roundtrip()
})
