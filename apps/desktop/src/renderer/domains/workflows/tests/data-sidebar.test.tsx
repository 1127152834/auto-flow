import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { findInternalIds } from '../../../shared/testing/internal-id-scan'
import { credentialApi } from '../api'
import { DataSidebar } from '../components/DataSidebar'
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'

const UUID = '3f2b8c1e-9a4d-4e7b-8c21-5d6e7f8a9b0c'
const writeText = vi.fn().mockResolvedValue(undefined)

const loadSignature = () => useSignatureStore.getState().load({
  inputs: [{ key: '账号', name: '账号信息', fields: [
    { key: 'phone', name: '手机号', type: 'string', required: true, sensitive: false, sample: '13800000000' },
    { key: 'pwd', name: '密码', type: 'string', required: false, sensitive: true },
  ] }],
})

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  writeText.mockClear()
  useSignatureStore.getState().reset()
  vi.spyOn(credentialApi, 'list').mockResolvedValue({ success: true, data: { success: true, credentials: [
    { name: '邮箱账号', description: '发信用', created_at: '', updated_at: '', fields: [{ key: 'password', masked: '****' }] },
  ] } } as never)
  useWorkflowStore.setState({
    nodes: [
      { id: UUID, position: { x: 0, y: 0 }, data: { label: '读取标题', moduleType: 'get_element_info', variableName: 'title' } },
      { id: 'n2', position: { x: 0, y: 0 }, selected: true, data: { label: '打印', moduleType: 'print_log', message: '{input.账号.phone}' } },
    ] as never,
    edges: [{ id: 'e', source: UUID, target: 'n2' }] as never,
    variables: [{ name: 'count', value: 3, type: 'number', scope: 'global' }] as never,
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('DataSidebar', () => {
  it('空状态给业务化提示', async () => {
    useWorkflowStore.setState({ nodes: [], edges: [], variables: [] })
    vi.spyOn(credentialApi, 'list').mockResolvedValue({ success: true, data: { success: true, credentials: [] } } as never)
    render(<DataSidebar />)
    expect(screen.getByText(/还没有输入字段，可在“输入与输出”里添加/)).toBeTruthy()
    await waitFor(() => expect(screen.getByText(/还没有凭据/)).toBeTruthy())
  })

  it('四个分组都显示，凭据不显示值，且不泄漏内部标识', async () => {
    loadSignature()
    const { container } = render(<DataSidebar />)
    for (const name of ['输入字段', '节点输出', '全局变量', '凭据']) expect(screen.getByRole('heading', { name })).toBeTruthy()
    await screen.findByText('邮箱账号')
    expect(screen.getByText('发信用')).toBeTruthy()
    expect(container.textContent).not.toContain('****')
    expect(screen.getByText('读取标题·结果')).toBeTruthy()
    expect(findInternalIds(container)).toEqual([])
  })

  it('搜索过滤，无结果时给提示', () => {
    loadSignature()
    render(<DataSidebar />)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '手机' } })
    expect(screen.getByText('手机号')).toBeTruthy()
    expect(screen.queryByText('count')).toBeNull()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '不存在的东西' } })
    expect(screen.getByText(/没有匹配的数据/)).toBeTruthy()
  })

  it('悬停或聚焦显示类型、来源、样例；敏感样例打码', () => {
    loadSignature()
    render(<DataSidebar />)
    const row = screen.getByRole('button', { name: /手机号/ })
    fireEvent.mouseEnter(row)
    const tip = screen.getByRole('tooltip')
    expect(tip.textContent).toContain('文本')
    expect(tip.textContent).toContain('账号信息')
    expect(tip.textContent).toContain('13800000000')
    fireEvent.mouseLeave(row)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.focus(screen.getByRole('button', { name: /密码/ }))
    expect(screen.getByRole('tooltip').textContent).toContain('••••••')
    expect(screen.getByRole('tooltip').textContent).not.toContain('13800000000')
  })

  it('点击复制引用并提示（role=status），键盘可达', async () => {
    loadSignature()
    render(<DataSidebar />)
    const row = screen.getByRole('button', { name: /手机号/ })
    expect(row.tagName).toBe('BUTTON')
    await act(async () => { fireEvent.click(row) })
    expect(writeText).toHaveBeenCalledWith('{input.账号.phone}')
    expect(screen.getByRole('status').textContent).toContain('已复制引用')
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /count/ })) })
    expect(writeText).toHaveBeenLastCalledWith('{count}')
  })

  it('复制失败时说明原因', async () => {
    loadSignature()
    writeText.mockRejectedValueOnce(new Error('拒绝访问'))
    render(<DataSidebar />)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /手机号/ })) })
    expect(screen.getByRole('status').textContent).toMatch(/没能复制.*拒绝访问/)
  })

  it('选中的画布节点引用的数据行高亮', () => {
    loadSignature()
    render(<DataSidebar />)
    expect(screen.getByRole('button', { name: /手机号/ }).getAttribute('data-highlighted')).toBe('true')
    expect(screen.getByRole('button', { name: /密码/ }).getAttribute('data-highlighted')).toBeNull()
  })

  it('凭据读取失败时显示原因', async () => {
    vi.spyOn(credentialApi, 'list').mockResolvedValue({ success: false, error: '服务未启动' } as never)
    render(<DataSidebar />)
    await waitFor(() => expect(screen.getByText(/读取凭据失败.*服务未启动/)).toBeTruthy())
  })
})
