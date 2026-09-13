import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { RecordStatusDialog, type RecordStatusDialogProps } from './RecordStatusDialog'

type Schema = components['schemas']
const record: Schema['DataRecordView'] = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '001' } }, values: [], recordSlots: [], statusId: 's1', currentEnvironmentId: null, contentRevision: 1, statusRevision: 2, linkRevision: 1, deleted: false, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' }
const status = (id: string): Schema['DataStatusView'] => ({ statusId: id, name: id === 's1' ? '待处理' : '已完成', color: '#a86f4c', order: 0, statusRevision: 1 })
function props(extra: Partial<RecordStatusDialogProps> = {}): RecordStatusDialogProps { return { open: true, sessionKey: 'session', submissionEpoch: 'i1', record, statuses: [status('s1'), status('s2')], readonly: false, saving: false, recoveryPending: false, error: null, onSubmit: vi.fn().mockResolvedValue(undefined), onRecover: vi.fn().mockResolvedValue(undefined), onDirtyChange: vi.fn(), onSavingChange: vi.fn(), onRequestClose: vi.fn().mockResolvedValue(false), onOpenChange: vi.fn(), ...extra } }
afterEach(cleanup); choiceTestEnvironment()

it('submits only explicit changed status and represents clearing as null', async () => {
  const p = props(); render(<RecordStatusDialog {...p} />)
  expect(screen.getByRole('button', { name: '保存状态' })).toBeDisabled()
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '记录业务状态' }), '__unset__')
  expect(p.onDirtyChange).toHaveBeenLastCalledWith(true)
  await userEvent.click(screen.getByRole('button', { name: '保存状态' }))
  expect(p.onSubmit).toHaveBeenCalledWith(null)
  expect(p.onOpenChange).not.toHaveBeenCalled()
})

it('allows an explicit null write from a null baseline while unchanged non-null stays disabled', async () => {
  const cleared = props({ record: { ...record, statusId: null } })
  const view = render(<RecordStatusDialog {...cleared} />)
  expect(screen.getByRole('button', { name: '保存状态' })).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '保存状态' }))
  expect(cleared.onSubmit).toHaveBeenCalledWith(null)

  view.rerender(<RecordStatusDialog {...cleared} sessionKey="assigned" record={record} />)
  expect(screen.getByRole('button', { name: '保存状态' })).toBeDisabled()
})

it('preserves dirty selection across refresh and reconnect but resets a new session', async () => {
  const p = props(); const view = render(<RecordStatusDialog {...p} />)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '记录业务状态' }), 's2')
  view.rerender(<RecordStatusDialog {...p} submissionEpoch="i2" record={{ ...record, statusId: null }} />)
  expect(screen.getByRole('combobox')).toHaveTextContent('已完成')
  view.rerender(<RecordStatusDialog {...p} sessionKey="next" record={{ ...record, statusId: null }} />)
  expect(screen.getByRole('combobox')).toHaveTextContent('未设置')
})

it('does not silently substitute for a missing original status', () => {
  render(<RecordStatusDialog {...props({ statuses: [status('s2')] })} />)
  expect(screen.getByRole('alert')).toHaveTextContent('原状态已不可用')
  expect(screen.getByRole('button', { name: '保存状态' })).toBeDisabled()
})

it('keeps recovery available after reconnection and ignores late old errors', async () => {
  let reject!: (error: Error) => void
  const p = props({ onSubmit: vi.fn(() => new Promise((_resolve, no) => { reject = no })) })
  const view = render(<RecordStatusDialog {...p} />)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox'), 's2')
  await userEvent.click(screen.getByRole('button', { name: '保存状态' }))
  expect(p.onSavingChange).toHaveBeenLastCalledWith(true)
  view.rerender(<RecordStatusDialog {...p} submissionEpoch="i2" readonly recoveryPending />)
  await userEvent.click(screen.getByRole('button', { name: '核对保存结果' }))
  expect(p.onRecover).toHaveBeenCalledOnce()
  await act(async () => reject(new Error('旧失败')))
  expect(screen.queryByText('旧失败')).not.toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(p.onOpenChange).not.toHaveBeenCalled()
})

it('rechecks close approval and reports clean teardown', async () => {
  let allow!: (allowed: boolean) => void
  const p = props({ onRequestClose: () => new Promise<boolean>(resolve => { allow = resolve }) })
  const view = render(<RecordStatusDialog {...p} />)
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  view.rerender(<RecordStatusDialog {...p} saving />)
  await act(async () => allow(true))
  expect(p.onOpenChange).not.toHaveBeenCalled()
  view.unmount()
  expect(p.onDirtyChange).toHaveBeenLastCalledWith(false)
  expect(p.onSavingChange).toHaveBeenLastCalledWith(false)
})

it.each([false, true])('renders the new session baseline when it equals the prior selection (trimmed catalog: %s)', async trimmed => {
  const p = props(); const view = render(<RecordStatusDialog {...p} />)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox'), 's2')
  view.rerender(<RecordStatusDialog {...p} sessionKey="next" record={{ ...record, statusId: 's2' }} statuses={trimmed ? [status('s2')] : p.statuses} />)
  expect(screen.queryByText('原状态已不可用，请载入最新资料。')).not.toBeInTheDocument()
  expect(screen.getByRole('combobox')).not.toBeDisabled()
  expect(screen.getByRole('button', { name: '保存状态' })).toBeDisabled()
  expect(p.onDirtyChange).toHaveBeenLastCalledWith(false)
})

it('renders inline without a dialog and cancels a draft back to its baseline', async () => {
  const p=props({presentation:'inline'}),user=userEvent.setup();render(<RecordStatusDialog {...p}/>)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  await chooseOption(user,screen.getByRole('combobox',{name:'记录业务状态'}),'s2');expect(screen.getByRole('button',{name:'保存状态'})).toBeEnabled()
  await user.click(screen.getByRole('button',{name:'取消'}));expect(screen.getByRole('combobox')).toHaveTextContent('待处理');expect(p.onDirtyChange).toHaveBeenLastCalledWith(false)
  await chooseOption(user,screen.getByRole('combobox',{name:'记录业务状态'}),'s2');await user.click(screen.getByRole('button',{name:'保存状态'}));expect(p.onSubmit).toHaveBeenCalledWith('s2')
})

it('inline clear explicitly submits null even from a null baseline', async () => {
  const p=props({presentation:'inline',record:{...record,statusId:null}});render(<RecordStatusDialog {...p}/>)
  await userEvent.click(screen.getByRole('button',{name:'清空状态'}));expect(p.onSubmit).toHaveBeenCalledWith(null);expect(p.onOpenChange).not.toHaveBeenCalled()
})
