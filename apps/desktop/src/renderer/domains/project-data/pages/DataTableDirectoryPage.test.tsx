import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type ApiRequestInit, type StreamingApiClient } from '../../../shared/api/client'
import type { DataTable } from '../api'
import { DataTableDirectoryPage, type DataTableDirectoryPageProps } from './DataTableDirectoryPage'

const table: DataTable = { projectId: 'p', tableId: 't', name: '客户数据', description: '说明', sourceKind: 'local', datasetGeneration: 'g', tableRevision: 3, identity: { mode: 'system' }, slotDefinitions: [], recordCount: 7, syncSummary: { status: 'notApplicable', pendingCount: 0, unknownCount: 0, lastConfirmedAt: null }, createdAt: '2026-09-13T09:00:00Z', updatedAt: '2026-09-13T10:00:00Z' }
const page = (items = [table], total = items.length) => ({ items, total, page: 1, pageSize: 50, sort: '-updatedAt' })
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; return { promise: new Promise<T>((yes, no) => { resolve = yes; reject = no }), resolve, reject } }
function mount(request: StreamingApiClient['request'], override: Partial<DataTableDirectoryPageProps> = {}) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const props: DataTableDirectoryPageProps = { projectId: 'p', workspaceKey: 'w1', instanceId: 'i1', client: { request, stream: vi.fn(), health: vi.fn() }, disabled: false, readonly: false, onOpen: vi.fn(), registerLeaveGuard: vi.fn(), ...override }
  const tree = (next: Partial<DataTableDirectoryPageProps> = {}) => <QueryClientProvider client={cache}><DataTableDirectoryPage {...props} {...next} /></QueryClientProvider>
  const view = render(tree())
  return { ...view, props, cache, update: (next: Partial<DataTableDirectoryPageProps>) => view.rerender(tree(next)) }
}
beforeEach(() => { sessionStorage.clear(); vi.stubGlobal('ResizeObserver', class { observe() {}; unobserve() {}; disconnect() {} }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('queries the real data API with scoped filters, paging, and cancelable reads', async () => {
  const request = vi.fn(async () => page([table], 70))
  const view = mount(request as StreamingApiClient['request'])
  expect(await screen.findByText('7 条记录')).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('/projects/p/tables?q=&page=1&pageSize=50&sort=-updatedAt'), expect.objectContaining({ signal: expect.any(AbortSignal) }))
  await userEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(request).toHaveBeenLastCalledWith(expect.stringContaining('page=2'), expect.anything()))
  await userEvent.type(screen.getByLabelText('搜索数据表'), '客户')
  await waitFor(() => expect(request).toHaveBeenLastCalledWith(expect.stringContaining('q=%E5%AE%A2%E6%88%B7&page=1'), expect.anything()))
  view.unmount()
  mount(request as StreamingApiClient['request'])
  expect(screen.getByLabelText('搜索数据表')).toHaveValue('客户')
})

it('creates a local table, invalidates the real directory, and clears guard before open', async () => {
  let guard: (() => Promise<boolean>) | null = null
  const opened = vi.fn()
  const request = vi.fn(async (_path: string, init?: ApiRequestInit) => init?.method === 'POST' ? table : page([]))
  mount(request as StreamingApiClient['request'], { registerLeaveGuard: value => { guard = value }, onOpen: id => { void guard?.().then(allowed => { if (allowed) opened(id) }) } })
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), ' 客户数据 ')
  await userEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  await waitFor(() => expect(opened).toHaveBeenCalledWith('t'))
  expect(request.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]).toMatchObject({ body: { name: '客户数据', description: '' }, headers: { 'Idempotency-Key': expect.any(String) } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('keeps the original table revision and draft on refresh, then explicitly reloads after conflict', async () => {
  let current = table
  const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
    if (init?.method === 'PATCH') throw new ApiClientError('数据表已被修改', 409, 'REVISION_CONFLICT')
    return path.includes('?') ? page([current]) : current
  })
  const view = mount(request as StreamingApiClient['request'])
  await userEvent.click(await screen.findByRole('button', { name: '编辑客户数据' }))
  await userEvent.clear(screen.getByLabelText('数据表名称')); await userEvent.type(screen.getByLabelText('数据表名称'), '我的草稿')
  current = { ...table, name: '远端新名称', tableRevision: 4 }
  await act(async () => { await view.cache.invalidateQueries() })
  expect(screen.getByLabelText('数据表名称')).toHaveValue('我的草稿')
  await userEvent.click(screen.getByRole('button', { name: '保存修改' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('数据表已被修改')
  expect(request.mock.calls.find(([, init]) => init?.method === 'PATCH')?.[1]?.body).toMatchObject({ expectedTableRevision: 3, name: '我的草稿' })
  await userEvent.click(screen.getByRole('button', { name: '载入最新资料' }))
  expect(screen.getByRole('alertdialog')).toHaveTextContent('替换当前草稿')
  expect(request.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: '重新编辑' }))
  await waitFor(() => expect(screen.getByLabelText('数据表名称')).toHaveValue('远端新名称'))
})

it('retains the original key and freezes an unknown command until lookup succeeds', async () => {
  let lookups = 0, key = ''
  const request = vi.fn(async (path: string, init?: ApiRequestInit) => {
    if (init?.method === 'POST') { key = new Headers(init.headers).get('Idempotency-Key')!; throw new TypeError('连接中断') }
    if (path.includes('/operations/')) {
      if (++lookups === 1) throw new TypeError('仍未恢复')
      return { projectId: 'p', idempotencyKey: key, kind: 'createTable', status: 'succeeded', resource: { type: 'table', projectId: 'p', tableId: 't' }, result: table }
    }
    return page([])
  })
  const view = mount(request as StreamingApiClient['request'])
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '客户数据')
  await userEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('结果尚未确认')
  expect(screen.getByLabelText('数据表名称')).toHaveAttribute('readonly')
  await userEvent.click(screen.getByRole('button', { name: '核对保存结果' }))
  await waitFor(() => expect(view.props.onOpen).toHaveBeenCalledWith('t'))
  expect(request.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  expect(lookups).toBe(2)
})

it('protects dirty navigation and clears the guard after explicit discard', async () => {
  let guard: (() => Promise<boolean>) | null = null
  mount(vi.fn().mockResolvedValue(page([])), { registerLeaveGuard: value => { guard = value } })
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  let result!: Promise<boolean>
  act(() => { result = guard!() })
  await userEvent.click(screen.getByRole('button', { name: '继续编辑' }))
  expect(await result).toBe(false)
  act(() => { result = guard!() })
  await userEvent.click(screen.getByRole('button', { name: '放弃修改' }))
  expect(await result).toBe(true)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('keeps same-workspace reconnect drafts and rejects late old-instance success', async () => {
  const pending = deferred<DataTable>()
  const request = vi.fn((_path: string, init?: ApiRequestInit) => init?.method === 'POST' ? pending.promise : Promise.resolve(page([])))
  const view = mount(request as StreamingApiClient['request'])
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '草稿')
  await userEvent.click(screen.getByRole('button', { name: '创建数据表' }))
  view.update({ instanceId: 'i2' })
  await act(async () => { pending.resolve(table) })
  expect(screen.getByLabelText('数据表名称')).toHaveValue('草稿')
  expect(view.props.onOpen).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: '核对保存结果' })).toBeEnabled()
})

it('cancels old reads and resets editor when changing workspace or project', async () => {
  let signal: AbortSignal | undefined
  const request = vi.fn((_path: string, init?: ApiRequestInit) => { signal ??= init?.signal ?? undefined; return Promise.resolve(page([])) })
  const view = mount(request as StreamingApiClient['request'])
  await userEvent.click(await screen.findByRole('button', { name: '新建数据表' }))
  await userEvent.type(screen.getByLabelText('数据表名称'), '旧工作区')
  view.update({ workspaceKey: 'w2', projectId: 'p2' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await waitFor(() => expect(request).toHaveBeenLastCalledWith(expect.stringContaining('/projects/p2/tables'), expect.anything()))
  expect(signal).toBeInstanceOf(AbortSignal)
})

it('shows explicit initial-load failure, and readonly data remains openable', async () => {
  const request = vi.fn().mockRejectedValue(new Error('无法连接'))
  const view = mount(request, { readonly: true })
  expect(await screen.findByRole('alert')).toHaveTextContent('无法连接')
  expect(screen.queryByText(/上次成功/)).not.toBeInTheDocument()
  request.mockResolvedValue(page())
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  await userEvent.click(await screen.findByRole('button', { name: '打开客户数据' }))
  expect(view.props.onOpen).toHaveBeenCalledWith('t')
  expect(screen.queryByRole('button', { name: '新建数据表' })).not.toBeInTheDocument()
})
