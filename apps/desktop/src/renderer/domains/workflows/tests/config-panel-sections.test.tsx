import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
const rules = vi.hoisted(() => ({
  data: {
    schemaRevision: 't',
    coveredModules: ['click_element', 'get_element_info', 'close_page'],
    requiredFields: { click_element: ['selector'], get_element_info: ['selector', 'columnName'], close_page: [] } as Record<string, string[]>,
    conditionalRequired: {},
    fieldLabels: { get_element_info: { columnName: '存储到数据表列' }, click_element: { selector: '元素选择器' } },
  },
}))
vi.mock('../lib/requiredFields', async importOriginal => ({
  ...(await importOriginal<typeof import('../lib/requiredFields')>()),
  useRequiredFields: () => ({ data: rules.data, loading: false, error: null, retry: () => {} }),
}))
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { elementPickerApi } from '../api'

Element.prototype.scrollIntoView = vi.fn()
let id: string
function mount(type: string, data: Record<string, unknown> = {}) {
  store.getState().clearWorkflow()
  store.getState().addNode(type as 'wait', { x: 0, y: 0 }, data)
  id = store.getState().nodes[0].id
  return render(<ConfigPanel selectedNodeId={id} />)
}
const advancedToggle = () => screen.getByRole('button', { name: /高级设置/ })
const ok = (count: number) => ({ success: true, data: { success: true, matched: count > 0, count } }) as never
const flush = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

beforeEach(() => { vi.useFakeTimers(); vi.spyOn(elementPickerApi, 'testSelector').mockResolvedValue(ok(3)) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

describe('分基本 / 高级', () => {
  it('试点节点：基本字段直接显示，高级字段与超时、出错处理默认折叠，点击后展开', () => {
    mount('click_element', { selector: '#a' })
    expect(screen.getByText('点击类型')).toBeInTheDocument()
    expect(screen.queryByText('点击后跟进新标签页')).toBeNull()
    expect(screen.queryByText('超时时间 (秒)')).toBeNull()
    expect(advancedToggle()).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(advancedToggle())
    expect(advancedToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('点击后跟进新标签页')).toBeInTheDocument()
    expect(screen.getByText('超时时间 (秒)')).toBeInTheDocument()
    expect(screen.getByText('出错时')).toBeInTheDocument()
  })

  it('非试点节点：模块字段全部留在基本区，只有通用项在高级区', () => {
    mount('close_page')
    expect(screen.queryByText('超时时间 (秒)')).toBeNull()
    fireEvent.click(advancedToggle())
    expect(screen.getByText('超时时间 (秒)')).toBeInTheDocument()
  })

  it('同一节点的高级区不会随重新选择而丢失已填值', () => {
    mount('click_element', { selector: '#a', followNewTab: true })
    fireEvent.click(advancedToggle())
    expect(screen.getByRole('checkbox', { name: /点击后跟进新标签页/ })).toHaveAttribute('aria-checked', 'true')
  })
})

describe('字段级错误与汇总', () => {
  it('汇总条显示 N 项必填未填；点击后聚焦首个错误字段', () => {
    mount('click_element', {})
    const summary = screen.getByRole('button', { name: /1 项必填未填/ })
    fireEvent.click(summary)
    expect(document.activeElement).toBe(screen.getByPlaceholderText('例如: #button, .submit'))
    expect(screen.getByRole('alert')).toHaveTextContent('还没填写')
  })

  it('错误显示在字段下方并带 aria-invalid', () => {
    mount('click_element', {})
    const input = screen.getByPlaceholderText('例如: #button, .submit')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input.closest('[data-config-field="selector"]')!.querySelector('[role="alert"]')).not.toBeNull()
  })

  it('错误落在高级字段时，高级区自动展开并能聚焦到该字段', () => {
    mount('get_element_info', { selector: '#t' })
    expect(advancedToggle()).toHaveAttribute('aria-expanded', 'true')
    const alert = screen.getAllByRole('alert').find(a => a.textContent?.includes('存储到数据表列'))!
    expect(alert).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /1 项必填未填/ }))
    expect(document.activeElement).toBe(screen.getByPlaceholderText('列名(可选)'))
  })

  it('没有错误时不显示汇总条', () => {
    mount('click_element', { selector: '#a' })
    expect(screen.queryByRole('button', { name: /必填未填/ })).toBeNull()
  })
})

describe('选择器匹配数', () => {
  it('防抖后显示当前页面匹配数', async () => {
    mount('click_element', { selector: '#a' })
    expect(screen.getByText('正在检查匹配数…')).toBeInTheDocument()
    await flush(500)
    expect(screen.getByText('当前页面匹配 3 个元素')).toBeInTheDocument()
  })

  it('未连接浏览器时给出提示，且请求不高亮', async () => {
    vi.spyOn(elementPickerApi, 'testSelector').mockResolvedValue({ success: true, data: { success: false, error: '浏览器未打开' } } as never)
    mount('click_element', { selector: '#a' })
    await flush(500)
    expect(screen.getByText('未连接浏览器')).toBeInTheDocument()
    expect(elementPickerApi.testSelector).toHaveBeenCalledWith('#a', undefined, false)
  })

  it('检查失败提示可点击测试重试', async () => {
    vi.spyOn(elementPickerApi, 'testSelector').mockRejectedValue(new Error('boom'))
    mount('click_element', { selector: '#a' })
    await flush(500)
    expect(screen.getByText('检查失败，可点击测试重试')).toBeInTheDocument()
  })

  it('工作流运行中不检查', async () => {
    mount('click_element', { selector: '#a' })
    act(() => store.getState().setExecutionStatus('running'))
    await flush(1000)
    expect(screen.getByText('运行中不检查')).toBeInTheDocument()
    expect(elementPickerApi.testSelector).not.toHaveBeenCalled()
    store.getState().setExecutionStatus('pending')
  })

  it('选择器为空时不显示匹配数', async () => {
    mount('click_element', {})
    await flush(1000)
    expect(screen.queryByText(/匹配/)).toBeNull()
  })
})
