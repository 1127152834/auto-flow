import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { ProcessingUnitsPanel, type ProcessingUnit } from './ProcessingUnitsPanel'

choiceTestEnvironment()
afterEach(cleanup)

const unit = (value: string, state: ProcessingUnit['state'], extra: Partial<ProcessingUnit> = {}): ProcessingUnit => ({
  unitId: `u-${value}`, processingInputId: 'i1', identityNamespace: null, state, attempts: 1, processingCycle: 1, cycleAttempts: 1,
  recordRef: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value } },
  lastOutcome: null, lastError: null, lastTaskId: null, lastAt: null, nextEligibleAt: null, revision: 3, review: null, ...extra,
})

function api(items: ProcessingUnit[]) {
  return {
    list: vi.fn(async () => ({ items, nextAfter: null })),
    command: vi.fn(async (_unitId: string, action: string, _body: object, _key: string) => ({ unit: { ...items[0], state: action === 'skip' ? 'skipped' as const : 'pending' as const, revision: 4 } })),
  }
}

it('lists units with user-facing states and the last reason, never internal identifiers', async () => {
  const client = api([unit('订单-1', 'failed_retryable', { lastOutcome: 'page', lastError: { code: 'WORKFLOW_NODE_TIMEOUT', message: '工作流节点执行超时：节点在 30 秒内未完成' } }), unit('订单-2', 'needs_review', { lastOutcome: 'unknown' })])
  render(<ProcessingUnitsPanel api={client}/>)
  const first = await screen.findByRole('row', { name: /订单-1/ })
  expect(within(first).getByText('失败，稍后重试')).toBeVisible()
  expect(within(first).getByText('工作流节点执行超时：节点在 30 秒内未完成')).toBeVisible()
  expect(within(screen.getByRole('row', { name: /订单-2/ })).getByText('结果不明，需要核实')).toBeVisible()
  expect(screen.queryByText(/datasetGeneration|RecordRef|g$/)).toBeNull()
})

it('filters by state', async () => {
  const client = api([])
  render(<ProcessingUnitsPanel api={client}/>)
  await waitFor(() => expect(client.list).toHaveBeenCalledWith(null, null))
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '处理状态' }), 'needs_review')
  await waitFor(() => expect(client.list).toHaveBeenLastCalledWith('needs_review', null))
})

it('skips with a reason and the revision the person saw', async () => {
  const client = api([unit('订单-1', 'pending')])
  render(<ProcessingUnitsPanel api={client}/>)
  fireEvent.click(await screen.findByRole('button', { name: '跳过 订单-1' }))
  const confirm = screen.getByRole('button', { name: '确认跳过' })
  expect(confirm).toBeDisabled()
  fireEvent.change(screen.getByRole('textbox', { name: '原因' }), { target: { value: '这条不用处理' } })
  fireEvent.click(confirm)
  await waitFor(() => expect(client.command).toHaveBeenCalledWith('u-订单-1', 'skip', { expectedRevision: 3, reason: '这条不用处理' }, expect.any(String)))
})

it('offers only verification for a unit whose last result is unknown', async () => {
  const client = api([unit('订单-2', 'needs_review')])
  render(<ProcessingUnitsPanel api={client}/>)
  const row = await screen.findByRole('row', { name: /订单-2/ })
  expect(within(row).queryByRole('button', { name: /重置|跳过/ })).toBeNull()
  fireEvent.click(within(row).getByRole('button', { name: '核实 订单-2' }))
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '核实结论' }), 'confirmedNotPerformed')
  fireEvent.change(screen.getByRole('textbox', { name: '原因' }), { target: { value: '对方系统没有收到' } })
  fireEvent.click(screen.getByRole('button', { name: '确认核实' }))
  await waitFor(() => expect(client.command).toHaveBeenCalledWith('u-订单-2', 'resolve', { expectedRevision: 3, reason: '对方系统没有收到', decision: 'confirmedNotPerformed' }, expect.any(String)))
})

it('keeps the same request identity when a failed command is retried', async () => {
  const client = api([unit('订单-1', 'pending')])
  client.command.mockRejectedValueOnce(new Error('网络中断'))
  render(<ProcessingUnitsPanel api={client}/>)
  fireEvent.click(await screen.findByRole('button', { name: '跳过 订单-1' }))
  fireEvent.change(screen.getByRole('textbox', { name: '原因' }), { target: { value: '不处理' } })
  fireEvent.click(screen.getByRole('button', { name: '确认跳过' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作失败，请重试')
  fireEvent.click(screen.getByRole('button', { name: '确认跳过' }))
  await waitFor(() => expect(client.command).toHaveBeenCalledTimes(2))
  expect(client.command.mock.calls[0][3]).toBe(client.command.mock.calls[1][3])
})
