import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DebugPanel } from '../components/DebugPanel'
import { DebugStart } from '../components/DebugStart'
import { isRunActive, parseDebugValues } from '../run-types'
import { runApi, runRecord } from './run-fixtures'

afterEach(cleanup)

it('keeps pauses active and sends exactly one stable command while acknowledgment is pending', async () => {
  const api = runApi()
  vi.mocked(api.debugCommand).mockImplementation(async (_id, body) => ({ commandId: body.commandId, state: 'accepted' }))
  vi.mocked(api.debugCommandStatus).mockImplementation(async (_id, commandId) => ({ commandId, state: 'accepted' }))
  const run = runRecord({ mode: 'debug', state: 'paused', debug: { pauseId: 'p1', controlRevision: 4, breakpoints: [] } })
  expect(isRunActive(run)).toBe(true)
  render(<DebugPanel api={api} run={run} connected refresh={vi.fn()} stop={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '单步' }))
  fireEvent.click(screen.getByRole('button', { name: '单步' }))
  expect(api.debugCommand).toHaveBeenCalledTimes(1)
  expect(api.debugCommand).toHaveBeenCalledWith('run-1', expect.objectContaining({ action: 'step', pauseId: 'p1', expectedRevision: 4 }))
  await waitFor(() => expect(api.debugCommandStatus).toHaveBeenCalled())
  expect(screen.getByRole('button', { name: '单步' })).toBeDisabled()
})

it('does not resume with uncommitted variable edits and failure inspection stays read-only', async () => {
  const api = runApi(), stop = vi.fn()
  const props = { api, connected: true, refresh: vi.fn(), stop, run: runRecord({ mode: 'debug', state: 'paused', debug: { pauseId: 'p1', controlRevision: 1 } }) }
  const view = render(<DebugPanel {...props} />)
  fireEvent.change(screen.getByLabelText('修改运行变量'), { target: { value: '{"n":' } })
  fireEvent.click(screen.getByRole('button', { name: '继续' }))
  expect(api.debugCommand).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('尚未提交')
  view.rerender(<DebugPanel {...props} run={{ ...props.run, state: 'failed_paused' }} />)
  expect(isRunActive({ state: 'failed_paused' })).toBe(true)
  expect(screen.getByRole('button', { name: '继续' })).toBeDisabled()
  expect(screen.queryByLabelText('修改运行变量')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '结束调试' }))
  expect(stop).toHaveBeenCalledOnce()
})

it('captures typed literal start inputs and requires selection for direct entry', () => {
  const start = vi.fn()
  render(<DebugStart disabled={false} selectedId={null} onStart={start} />)
  fireEvent.change(screen.getByLabelText('本次调试初值'), { target: { value: '{"n":3,"text":"{literal}"}' } })
  fireEvent.click(screen.getByRole('button', { name: '开始调试', hidden: true }))
  expect(start).toHaveBeenCalledWith(expect.objectContaining({ values: { n: 3, text: '{literal}' }, start: 'entry' }))
  fireEvent.change(screen.getByLabelText('调试起跑方式'), { target: { value: 'node' } })
  expect(screen.getByRole('button', { name: '开始调试', hidden: true })).toBeDisabled()
})

it('ignores late variable pagination after the paused checkpoint changes', async () => {
  const api = runApi()
  let resolveOld!: (value: Awaited<ReturnType<typeof api.variables>>) => void
  vi.mocked(api.variables).mockImplementation(async (_id, point, offset) => {
    if (offset) return new Promise(resolve => { resolveOld = resolve })
    return { checkpointId: point, items: [{ name: point === 'new' ? 'current' : 'before', preview: '1' }], nextOffset: 50 }
  })
  const props = { api, connected: true, refresh: vi.fn(), stop: vi.fn(), run: runRecord({ mode: 'debug', state: 'paused', debug: { checkpointId: 'old', pauseId: 'p1' } }) }
  const view = render(<DebugPanel {...props} />)
  await screen.findByRole('button', { name: /before/ })
  fireEvent.click(screen.getByRole('button', { name: '更多变量' }))
  view.rerender(<DebugPanel {...props} run={{ ...props.run, debug: { checkpointId: 'new', pauseId: 'p2' } }} />)
  await screen.findByRole('button', { name: /current/ })
  resolveOld({ checkpointId: 'old', items: [{ name: 'stale', preview: 'old' }] })
  await waitFor(() => expect(screen.queryByRole('button', { name: /stale/ })).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: /current/ })).toBeInTheDocument()
})

it('rejects overflowing JSON numbers before transport can silently turn them into null', () => {
  expect(() => parseDebugValues('{"list":[1e999]}')).toThrow('有限值')
  expect(parseDebugValues('{"list":[null,1,false],"text":"{literal}"}')).toEqual({ list: [null, 1, false], text: '{literal}' })
})
