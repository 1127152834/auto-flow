import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { BatchStartDialog } from './BatchStartDialog'
import { createBatchStartDraft } from '../start-schema'

afterEach(cleanup)
const definitions = [{ parameterId: 'n', name: '页数', type: 'number' as const, required: true, defaultValue: 0 }, { parameterId: 'b', name: '仅正文', type: 'boolean' as const, required: false, defaultValue: false }, { parameterId: 's', name: '备注', type: 'string' as const, required: false, defaultValue: '' }]
const checks = [{ label: '工作流', value: '资料整理流程', accepted: true, status: '可以运行' }]
const resources = [{ label: '浏览器配置', value: '商品资料采集' }, { label: '并发', value: '1' }]
it('submits stable parameter ids while preserving zero false and empty string', async () => {
  const onSubmit = vi.fn(), value = createBatchStartDraft(definitions, 10)
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={value} onChange={vi.fn()} onOpenChange={vi.fn()} onSubmit={onSubmit} checks={checks} resources={resources}/>)
  fireEvent.click(screen.getByRole('button', { name: '启动 10 个任务' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ expectedAutomationRevision: 7, parameters: { n: 0, b: false, s: '' }, maxTasks: 10, concurrency: 1 }))
})
it('keeps invalid controlled input visible and blocks submission', () => {
  const onSubmit = vi.fn(), value = { ...createBatchStartDraft(definitions), maxTasks: 'bad' }
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={value} onChange={vi.fn()} onOpenChange={vi.fn()} onSubmit={onSubmit} checks={checks} resources={resources} errorMessage="自动化资料已变化"/>)
  expect(screen.getByLabelText('本次任务数')).toHaveValue('bad'); expect(screen.getByText('自动化资料已变化')).toBeVisible(); expect(screen.getByRole('button', { name: '启动 bad 个任务' })).toBeDisabled(); expect(onSubmit).not.toHaveBeenCalled()
})
it('prevents closing and repeat submit while a start is pending', () => {
  const onOpenChange = vi.fn(), value = createBatchStartDraft(definitions)
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={value} onChange={vi.fn()} onOpenChange={onOpenChange} onSubmit={vi.fn()} checks={checks} resources={resources} submitting/>)
  fireEvent.click(screen.getByRole('button', { name: '取消' })); expect(onOpenChange).not.toHaveBeenCalled(); expect(screen.getByRole('button', { name: '启动 1 个任务' })).toHaveAttribute('aria-busy', 'true')
})
it('latches a pending submit before parent busy props update', async () => {
  let resolve!: () => void
  const pending = new Promise<void>(done => { resolve = done }), onSubmit = vi.fn(() => pending), onOpenChange = vi.fn()
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={createBatchStartDraft(definitions)} onChange={vi.fn()} onOpenChange={onOpenChange} onSubmit={onSubmit} checks={checks} resources={resources}/>)
  const start = screen.getByRole('button', { name: '启动 1 个任务' }); fireEvent.click(start); fireEvent.click(start); fireEvent.click(screen.getByRole('button', { name: '取消' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1)); expect(onOpenChange).not.toHaveBeenCalled(); expect(start).toHaveAttribute('aria-busy', 'true')
  resolve(); await pending
})
it('offers a controlled configuration repair action for blocked checks', () => {
  const onConfigure = vi.fn(), blocked = [{ label: '浏览器配置', value: '未配置', accepted: false, status: '需要配置' }]
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={createBatchStartDraft(definitions)} onChange={vi.fn()} onOpenChange={vi.fn()} onSubmit={vi.fn()} checks={blocked} resources={resources} onConfigure={onConfigure}/>)
  fireEvent.click(screen.getByRole('button', { name: '返回配置修复' })); expect(onConfigure).toHaveBeenCalledTimes(1); expect(screen.getByRole('button', { name: '启动 1 个任务' })).toBeDisabled()
})
it('does not clear the submit latch when the automation revision refreshes', async () => {
  let resolve!: () => void
  const pending = new Promise<void>(done => { resolve = done }), onSubmit = vi.fn(() => pending), value = createBatchStartDraft(definitions)
  const props = { formSessionKey: 'same-session', open: true, automationName: '资料整理', parameters: definitions, value, onChange: vi.fn(), onOpenChange: vi.fn(), onSubmit, checks, resources }
  const view = render(<BatchStartDialog {...props} expectedAutomationRevision={7}/>)
  fireEvent.click(screen.getByRole('button', { name: '启动 1 个任务' })); await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  view.rerender(<BatchStartDialog {...props} expectedAutomationRevision={8}/>)
  fireEvent.click(screen.getByRole('button', { name: '启动 1 个任务' })); expect(onSubmit).toHaveBeenCalledTimes(1)
  resolve(); await pending
})
it('surfaces deleted parameter errors and offers configuration repair', () => {
  const onConfigure = vi.fn(), value = createBatchStartDraft(definitions); value.parameters.deleted = { raw: '12' }
  render(<BatchStartDialog formSessionKey="session" open automationName="资料整理" expectedAutomationRevision={7} parameters={definitions} value={value} onChange={vi.fn()} onOpenChange={vi.fn()} onSubmit={vi.fn()} checks={checks} resources={resources} onConfigure={onConfigure}/>)
  expect(screen.getByRole('alert')).toHaveTextContent('参数已不存在')
  fireEvent.click(screen.getByRole('button', { name: '返回配置修复' })); expect(onConfigure).toHaveBeenCalledTimes(1)
})
