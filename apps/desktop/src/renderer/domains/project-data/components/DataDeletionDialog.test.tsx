import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { DataDeletionDialog, type DataDeletionDialogProps } from './DataDeletionDialog'

const impact: components['schemas']['DeletionImpactReport'] = { impactRevision: 2, target: { type: 'status', projectId: 'p', tableId: 't', statusId: 's' }, expectedRevisions: { tableRevision: 1, statusRevision: 1 }, changeDigest: 'digest', impacts: [], blockers: [], calculatedAt: '2026-09-13T00:00:00Z' }
function props(overrides: Partial<DataDeletionDialogProps> = {}): DataDeletionDialogProps {
  return { open: true, kind: 'status', targetName: '已完成', impact: null, saving: false, readonly: false, recoveryPending: false, error: null, onPreview: vi.fn().mockResolvedValue(undefined), onConfirm: vi.fn().mockResolvedValue(undefined), onRecover: vi.fn().mockResolvedValue(undefined), onRequestClose: vi.fn().mockResolvedValue(true), onOpenChange: vi.fn(), ...overrides }
}
afterEach(cleanup)

it('requires a real impact report and defaults danger-dialog focus to cancel', async () => {
  const p = props(); const view = render(<DataDeletionDialog {...p} />)
  expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
  expect(screen.queryByRole('button', { name: '确认删除' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '检查删除影响' }))
  expect(p.onPreview).toHaveBeenCalledOnce(); expect(p.onConfirm).not.toHaveBeenCalled()
  view.rerender(<DataDeletionDialog {...p} impact={impact} />)
  await userEvent.click(screen.getByRole('button', { name: '确认删除' }))
  expect(p.onConfirm).toHaveBeenCalledOnce()
  expect(p.onOpenChange).not.toHaveBeenCalled()
})

it('shows blockers and never offers an enabled confirmation for them', () => {
  render(<DataDeletionDialog {...props({ impact: { ...impact, blockers: [{ code: 'STATUS_IN_USE', message: '还有记录使用此状态', resource: impact.target, state: 'active' }] } })} />)
  expect(screen.getByRole('alert')).toHaveTextContent('还有记录使用此状态')
  expect(screen.getByRole('button', { name: '确认删除' })).toBeDisabled()
})

it('revokes confirmation when the parent invalidates an expired impact', () => {
  const p = props({ impact }); const view = render(<DataDeletionDialog {...p} />)
  expect(screen.getByRole('button', { name: '确认删除' })).toBeEnabled()
  view.rerender(<DataDeletionDialog {...p} impact={null} error="删除影响已变化，请重新检查" />)
  expect(screen.queryByRole('button', { name: '确认删除' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '检查删除影响' })).toBeEnabled()
})

it('permits readonly result lookup but freezes delete and close while outcome is unknown', async () => {
  const p = props({ impact, readonly: true, recoveryPending: true }); render(<DataDeletionDialog {...p} />)
  await userEvent.click(screen.getByRole('button', { name: '核对删除结果' }))
  expect(p.onRecover).toHaveBeenCalledOnce()
  expect(p.onConfirm).not.toHaveBeenCalled()
  await userEvent.keyboard('{Escape}')
  expect(p.onOpenChange).not.toHaveBeenCalled()
})

it('does not close when delayed approval arrives after deletion starts', async () => {
  let allow!: (value: boolean) => void
  const p = props({ impact, onRequestClose: () => new Promise<boolean>(resolve => { allow = resolve }) })
  const view = render(<DataDeletionDialog {...p} />)
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  view.rerender(<DataDeletionDialog {...p} saving />)
  await act(async () => allow(true))
  expect(p.onOpenChange).not.toHaveBeenCalled()
})

it('keeps preview rejection visible and prevents duplicate in-flight actions', async () => {
  let reject!: (error: Error) => void
  const p = props({ onPreview: vi.fn(() => new Promise((_resolve, no) => { reject = no })) })
  render(<DataDeletionDialog {...p} />)
  await userEvent.dblClick(screen.getByRole('button', { name: '检查删除影响' }))
  expect(p.onPreview).toHaveBeenCalledOnce()
  await act(async () => reject(new Error('无法读取引用')))
  expect(screen.getByRole('alert')).toHaveTextContent('无法读取引用')
  expect(screen.getByRole('button', { name: '检查删除影响' })).toBeEnabled()
})

it('can look up after reconnection without waiting for the revoked delete promise', async () => {
  let reject!: (error: Error) => void
  const p = props({ impact, onConfirm: vi.fn(() => new Promise((_resolve, no) => { reject = no })) })
  const view = render(<DataDeletionDialog {...p} submissionEpoch="i1" />)
  await userEvent.click(screen.getByRole('button', { name: '确认删除' }))
  view.rerender(<DataDeletionDialog {...p} submissionEpoch="i2" recoveryPending />)
  await userEvent.click(screen.getByRole('button', { name: '核对删除结果' }))
  expect(p.onRecover).toHaveBeenCalledOnce()
  await act(async () => reject(new Error('旧实例错误')))
  expect(screen.queryByText('旧实例错误')).not.toBeInTheDocument()
})

it('invalidates an older close approval even after a subsequent delete has failed', async () => {
  let allow!: (value: boolean) => void
  const p = props({ impact, onRequestClose: () => new Promise<boolean>(resolve => { allow = resolve }), onConfirm: vi.fn().mockRejectedValue(new Error('删除失败')) })
  render(<DataDeletionDialog {...p} />)
  await userEvent.click(screen.getByRole('button', { name: '取消' }))
  await userEvent.click(screen.getByRole('button', { name: '确认删除' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('删除失败')
  await act(async () => allow(true))
  expect(p.onOpenChange).not.toHaveBeenCalled()
})
