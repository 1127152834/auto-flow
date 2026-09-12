import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { RunPanel } from '../components/RunPanel'
import { RunToolbar } from '../components/RunToolbar'
import { runApi, runEvent, runRecord } from './run-fixtures'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('disables starting without a real selected profile and keeps stop available for an active run', async () => {
  const stop = vi.fn()
  const view = render(<RunToolbar profiles={[]} profileId="" onProfileChange={vi.fn()} active={null} busy={false} uncertain={false} disabled={false} profilesLoading={false} profilesError={false} onStart={vi.fn()} onStop={stop} onRefresh={vi.fn()} />)
  expect(screen.getByRole('button', { name: '运行当前草稿' })).toBeDisabled()
  view.rerender(<RunToolbar profiles={[]} profileId="profile-1" onProfileChange={vi.fn()} active={runRecord()} busy={false} uncertain={false} disabled={false} profilesLoading={false} profilesError={false} onStart={vi.fn()} onStop={stop} onRefresh={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '停止' }))
  expect(stop).toHaveBeenCalledOnce()
  expect(screen.getByRole('status')).toHaveTextContent('0/1 步')
})

it('names logs from the snapshot and only locates nodes when the current document agrees', async () => {
  const locate = vi.fn()
  const props = { run: runRecord(), events: [runEvent(1)], history: [], nextOffset: null, connected: true, message: null, api: runApi(), onSelect: vi.fn(), onLocate: locate, onMore: vi.fn() }
  const view = render(<RunPanel {...props} sameDocument={false} />)
  expect(screen.getByRole('button', { name: '快照节点' })).toBeDisabled()
  expect(screen.getByText(/画布与本次运行快照不同/)).toBeVisible()
  view.rerender(<RunPanel {...props} sameDocument />)
  await userEvent.click(screen.getByRole('button', { name: '快照节点' }))
  expect(locate).toHaveBeenCalledWith('node-1')
})

it('loads full JSON results through the authenticated API and presents them read-only', async () => {
  const api = runApi()
  const record = runRecord({ artifacts: [{ id: 'artifact-1', nodeId: 'node-1', kind: 'json', name: '提取结果', mimeType: 'application/json', relativePath: 'value.json', outputPath: null, preview: 'short preview' }] })
  render(<RunPanel run={record} events={[]} history={[]} nextOffset={null} sameDocument connected message={null} api={api} onSelect={vi.fn()} onLocate={vi.fn()} onMore={vi.fn()} />)
  await userEvent.click(screen.getByRole('tab', { name: /只读结果/ }))
  expect(api.artifact).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '查看完整结果' }))
  expect(await screen.findByLabelText('提取结果')).toHaveTextContent('{"actual":"result"}')
  expect(api.artifact).toHaveBeenCalledWith('run-1', 'artifact-1', expect.any(AbortSignal))
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

it('allows collapsing logs and stops following when the user scrolls up to inspect older events', async () => {
  const props = { run: runRecord(), events: [runEvent(1)], history: [], nextOffset: null, connected: true, message: null, api: runApi(), onSelect: vi.fn(), onLocate: vi.fn(), onMore: vi.fn(), sameDocument: true }
  const view = render(<RunPanel {...props} />)
  const area = screen.getByLabelText('日志内容')
  Object.defineProperties(area, { scrollHeight: { value: 1000 }, clientHeight: { value: 150 } })
  area.scrollTop = 100
  fireEvent.scroll(area)
  expect(screen.getByRole('checkbox', { name: '跟随最新' })).not.toBeChecked()
  view.rerender(<RunPanel {...props} events={[runEvent(1), runEvent(2)]} />)
  expect(area.scrollTop).toBe(100)
  await userEvent.click(screen.getByRole('checkbox', { name: '跟随最新' }))
  expect(area.scrollTop).toBe(1000)
  await userEvent.click(screen.getByRole('button', { name: '收起运行记录' }))
  expect(screen.queryByLabelText('日志内容')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '展开运行记录' }))
  expect(screen.getByText('真实事件 2')).toBeVisible()
})

it('renders a PNG from a fetched object URL and releases it when the result is collapsed', async () => {
  const createObjectURL = vi.fn(() => 'blob:local-artifact')
  const revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL, revokeObjectURL }))
  const api = runApi()
  const record = runRecord({ artifacts: [{ id: 'png-1', nodeId: 'node-1', kind: 'image', name: '网页截图', mimeType: 'image/png', relativePath: 'shot.png', outputPath: null, preview: '' }] })
  render(<RunPanel run={record} events={[]} history={[]} nextOffset={null} sameDocument connected message={null} api={api} onSelect={vi.fn()} onLocate={vi.fn()} onMore={vi.fn()} />)
  await userEvent.click(screen.getByRole('tab', { name: /只读结果/ }))
  expect(api.artifact).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '查看截图' }))
  expect(await screen.findByRole('img', { name: '网页截图' })).toHaveAttribute('src', 'blob:local-artifact')
  expect(createObjectURL).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('button', { name: '收起结果' }))
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:local-artifact')
})
