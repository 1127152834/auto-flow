import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import { createBlock } from '../components/blockFlowModel'
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

Element.prototype.scrollIntoView = vi.fn()

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

function renderNode(type: ModuleType) {
  store.getState().addNode(type, { x: 0, y: 0 })
  render(<ConfigPanel selectedNodeId={store.getState().nodes[0].id} />)
  return store.getState().nodes[0]
}
const value = (element: HTMLElement) => (element as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement).value

it('NODE.open_page.defaults-and-constraints: shows the frozen navigation defaults and an editable empty URL', () => {
  renderNode('open_page')
  expect(screen.getByRole('combobox', { name: '打开方式' }).textContent).toContain('新标签页')
  expect(screen.getByRole('combobox', { name: '等待条件' }).textContent).toContain('页面加载完成')
  expect(value(screen.getByPlaceholderText('https://example.com'))).toBe('')
})

it('NODE.use_opened_page.defaults-and-constraints: defaults to title matching without inventing a page identifier', () => {
  renderNode('use_opened_page')
  expect(screen.getByRole('combobox', { name: '匹配模式' }).textContent).toContain('按标题匹配')
  expect(value(screen.getByPlaceholderText('页面标题或URL的部分内容'))).toBe('')
})

it('NODE.click_element.defaults-and-constraints: defaults to a single click, no tab following and no selector', () => {
  renderNode('click_element')
  expect(screen.getByRole('combobox', { name: '点击类型' }).textContent).toContain('单击')
  expect(screen.getByRole('checkbox', { name: '点击后跟进新标签页' }).getAttribute('aria-checked')).toBe('false')
  expect(value(screen.getByPlaceholderText('例如: #button, .submit'))).toBe('')
})

it('NODE.input_text.defaults-and-constraints: defaults to clearing while preserving valid empty text and selector drafts', () => {
  renderNode('input_text')
  expect(screen.getByRole('checkbox', { name: '输入前清空原有内容' }).getAttribute('aria-checked')).toBe('true')
  expect(value(screen.getByPlaceholderText('例如: #input, .text-field'))).toBe('')
  expect(value(screen.getByPlaceholderText('要输入的文本内容'))).toBe('')
})

it('NODE.get_element_info.defaults-and-constraints: defaults to text and the stable output variable', () => {
  const node = renderNode('get_element_info')
  expect(screen.getByRole('combobox', { name: '获取属性' }).textContent).toContain('文本内容')
  expect(value(screen.getByPlaceholderText('变量名'))).toBe('element_value')
  expect(value(screen.getByPlaceholderText('列名(可选)'))).toBe('')
  expect(node.data.variableName).toBe('element_value')
})

it('NODE.wait_element.defaults-and-constraints: defaults to visible with the shared 60 second display budget', () => {
  renderNode('wait_element')
  expect(screen.getByRole('combobox', { name: '等待条件' }).textContent).toContain('可见')
  expect(value(screen.getByLabelText('超时时间(秒)'))).toBe('60')
  expect(value(screen.getByPlaceholderText('例如: #element, .class'))).toBe('')
})

it('NODE.screenshot.defaults-and-constraints: defaults to full page and keeps the stable result variable', () => {
  const node = renderNode('screenshot')
  expect(screen.getByRole('combobox', { name: '截图类型' }).textContent).toContain('整个页面')
  expect(screen.queryByPlaceholderText('#target')).toBeNull()
  expect(value(screen.getByPlaceholderText('保存文件路径的变量名'))).toBe('screenshot_path')
  expect(node.data.variableName).toBe('screenshot_path')
})

it('NODE.wait.defaults-and-constraints: defaults to an empty time wait without fabricating a duration', () => {
  renderNode('wait')
  expect(screen.getByRole('combobox', { name: '等待类型' }).textContent).toContain('等待时间')
  expect(value(screen.getByPlaceholderText('例如: 1 或 2.5'))).toBe('')
})

it.each(['firecrawl_map', 'firecrawl_crawl'] as const)('NODE.%s: new nodes persist the displayed Sitemap choice in both views', type => {
  const node = renderNode(type)
  expect(screen.getByRole('combobox', { name: '忽略 Sitemap' }).textContent).toContain('否')
  expect(node.data.ignoreSitemap).toBe(false)
  expect(createBlock(type).node.data.ignoreSitemap).toBe(false)
  store.getState().blockInsertNode(null, type)
  expect(store.getState().nodes.at(-1)?.data.ignoreSitemap).toBe(false)
  expect(createBlock(type, { ignoreSitemap: true }).node.data.ignoreSitemap).toBe(true)
})
