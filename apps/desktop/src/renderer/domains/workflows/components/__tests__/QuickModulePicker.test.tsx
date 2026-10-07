import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { Circle } from 'lucide-react'
import { QuickModulePicker, shouldOpenQuickPickerOnSlash } from '../QuickModulePicker'
import { useModuleStatsStore } from '../../hooks/stores/moduleStatsStore'
import type { ModuleType } from '../../types/index'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mods = [
  { type: 'click_element', label: '点击元素', category: '网页操作', icon: Circle },
  { type: 'input_text', label: '输入文本', category: '网页操作', icon: Circle },
  { type: 'delay', label: '等待', category: '流程控制', icon: Circle },
  { type: 'custom_module', label: '我的模块', category: '自定义', icon: Circle, isCustom: true, customModuleId: 'c1' },
] as Array<{ type: ModuleType; label: string; category: string; icon: React.ElementType; isCustom?: boolean; customModuleId?: string }>

let container: HTMLDivElement
let root: Root
const onSelect = vi.fn()
const onClose = vi.fn()

function render(props: Partial<React.ComponentProps<typeof QuickModulePicker>> = {}) {
  act(() => {
    root.render(
      <QuickModulePicker isOpen position={{ x: 400, y: 300 }} onClose={onClose} onSelectModule={onSelect} availableModules={mods} {...props} />,
    )
  })
}
const quick = () => container.querySelector('section[aria-label="最近与常用"]')
const items = (el: ParentNode = container) => Array.from(el.querySelectorAll<HTMLElement>('[data-quick-item]'))
const label = (e: HTMLElement) => e.querySelector('span')!.textContent
const input = () => container.querySelector('input') as HTMLInputElement
const type = (v: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
  act(() => {
    setter.call(input(), v)
    input().dispatchEvent(new Event('input', { bubbles: true }))
  })
}
const key = (el: Element, k: string) => act(() => { el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true })) })

beforeEach(() => {
  localStorage.clear()
  useModuleStatsStore.setState({
    stats: {
      delay: { usageCount: 9, lastUsed: 100, isFavorite: false },
      input_text: { usageCount: 1, lastUsed: 900, isFavorite: false },
      custom_module: { usageCount: 99, lastUsed: 999, isFavorite: false },
    } as never,
  })
  onSelect.mockClear()
  onClose.mockClear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('QuickModulePicker', () => {
  it('空搜索时置顶"最近与常用"，只含内置模块，全部模块仍可见', () => {
    render()
    const q = quick()!
    expect(q).toBeTruthy()
    expect(items(q).map(label).sort()).toEqual(['等待', '输入文本'])
    expect(container.textContent).toContain('点击元素')
    expect(container.textContent).toContain('我的模块')
    // 区块排在第一个分类之前
    const first = container.querySelector('[data-quick-item]')!
    expect(q.contains(first)).toBe(true)
  })

  it('没有使用记录时不显示该区块', () => {
    useModuleStatsStore.setState({ stats: {} })
    render()
    expect(quick()).toBeNull()
    expect(container.textContent).toContain('点击元素')
  })

  it('搜索时隐藏该区块并过滤全部模块', () => {
    render()
    type('点击')
    expect(quick()).toBeNull()
    expect(items().map(label)).toEqual(['点击元素'])
  })

  it('点击最近与常用中的模块会添加并关闭', () => {
    render()
    const target = items(quick()!).find((e) => label(e) === '等待')!
    act(() => target.click())
    expect(onSelect).toHaveBeenCalledWith('delay')
    expect(onClose).toHaveBeenCalled()
  })

  it('带来源节点与句柄时，选择结果原样带回来源', () => {
    const source = { nodeId: 'n1', handleId: 'error' }
    render({ source })
    act(() => items(quick()!).find((e) => label(e) === '等待')!.click())
    expect(onSelect).toHaveBeenCalledWith('delay', undefined, source)
  })

  it('键盘可达：模块项可聚焦，方向键在搜索框与列表间移动，Enter 选择', () => {
    render()
    const list = items()
    expect(list.every((e) => e.tabIndex === 0)).toBe(true)
    input().focus()
    key(input(), 'ArrowDown')
    expect(document.activeElement).toBe(list[0])
    key(list[0], 'ArrowDown')
    expect(document.activeElement).toBe(list[1])
    key(list[1], 'ArrowUp')
    expect(document.activeElement).toBe(list[0])
    key(list[0], 'ArrowUp')
    expect(document.activeElement).toBe(input())
    list[1].focus()
    key(list[1], 'Enter')
    expect(label(list[1])).toBe('等待')
    expect(onSelect).toHaveBeenCalledWith('delay')
  })

  it('收藏星标上按 Enter 或空格不会误添加模块，交给按钮自身处理', () => {
    render()
    const star = items()[0].querySelector('button')!
    for (const k of ['Enter', ' ']) {
      const event = new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true })
      act(() => { star.dispatchEvent(event) })
      expect(event.defaultPrevented).toBe(false)
    }
    expect(onSelect).not.toHaveBeenCalled()
    const row = items()[0]
    const onRow = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    act(() => { row.dispatchEvent(onRow) })
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('焦点可见：模块项与收藏按钮带 focus-visible 样式', () => {
    render()
    expect(items()[0].className).toContain('focus-visible:ring-2')
    expect(items()[0].querySelector('button')!.className).toContain('focus-visible:opacity-100')
  })
})

describe('shouldOpenQuickPickerOnSlash', () => {
  let canvas: HTMLDivElement
  beforeEach(() => {
    canvas = document.createElement('div')
    document.body.appendChild(canvas)
  })
  afterEach(() => canvas.remove())

  const ev = (target: Element, over: Record<string, unknown> = {}) =>
    ({ key: '/', ctrlKey: false, metaKey: false, altKey: false, defaultPrevented: false, isComposing: false, target, ...over }) as never
  const opts = (over = {}) => ({ pickerOpen: false, canvasEl: canvas, ...over })

  it('焦点在画布或 body 时触发', () => {
    expect(shouldOpenQuickPickerOnSlash(ev(canvas), opts())).toBe(true)
    expect(shouldOpenQuickPickerOnSlash(ev(document.body), opts())).toBe(true)
  })

  it.each(['input', 'textarea', 'select'])('%s 内不触发', (tag) => {
    const el = document.createElement(tag)
    canvas.appendChild(el)
    expect(shouldOpenQuickPickerOnSlash(ev(el), opts())).toBe(false)
  })

  it('contenteditable、CodeMirror、Monaco 内不触发', () => {
    const ce = document.createElement('div')
    ce.setAttribute('contenteditable', 'true')
    const cm = document.createElement('div')
    cm.className = 'cm-editor'
    const cmInner = document.createElement('div')
    cm.appendChild(cmInner)
    const mo = document.createElement('div')
    mo.className = 'monaco-editor'
    canvas.append(ce, cm, mo)
    expect(shouldOpenQuickPickerOnSlash(ev(ce), opts())).toBe(false)
    expect(shouldOpenQuickPickerOnSlash(ev(cmInner), opts())).toBe(false)
    expect(shouldOpenQuickPickerOnSlash(ev(mo), opts())).toBe(false)
  })

  it('有修饰键、其他按键、输入法组合时不触发', () => {
    for (const m of ['ctrlKey', 'metaKey', 'altKey']) {
      expect(shouldOpenQuickPickerOnSlash(ev(canvas, { [m]: true }), opts())).toBe(false)
    }
    expect(shouldOpenQuickPickerOnSlash(ev(canvas, { key: 'a' }), opts())).toBe(false)
    expect(shouldOpenQuickPickerOnSlash(ev(canvas, { isComposing: true }), opts())).toBe(false)
  })

  it('面板已打开、焦点在画布外或弹窗里时不触发', () => {
    expect(shouldOpenQuickPickerOnSlash(ev(canvas), opts({ pickerOpen: true }))).toBe(false)
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    expect(shouldOpenQuickPickerOnSlash(ev(outside), opts())).toBe(false)
    const dlg = document.createElement('div')
    dlg.setAttribute('role', 'dialog')
    canvas.appendChild(dlg)
    expect(shouldOpenQuickPickerOnSlash(ev(dlg), opts())).toBe(false)
    outside.remove()
  })
})
