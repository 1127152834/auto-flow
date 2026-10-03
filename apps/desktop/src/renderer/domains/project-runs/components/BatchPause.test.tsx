import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { BatchDetail, type BatchDetailProps } from './BatchDetail'
import { BatchStatus } from './BatchStatus'

afterEach(cleanup)

const paused = {
  batch: {
    batchId: 'b1', projectId: 'p', automationId: 'a', automationName: '注册账号', startOperationId: 'o', status: 'paused', statusRevision: 4,
    managementRevision: 1, requestedCount: 10, createdTaskCount: 5, activeTaskCount: 0, claimGateState: 'closed', createdAt: '2026-10-03T00:00:00Z', completedAt: null,
    selectionOutcome: { status: 'paused', pauseReason: { kind: 'infrastructureStreak', message: '连续 5 个任务在开始前因环境或代理问题失败，已暂停批次', code: 'PROXY_UNAVAILABLE', sampleTaskIds: ['t1'] } },
  },
  statusCounts: { failed: 5 }, taskCount: 5,
} as unknown as BatchDetailProps['detail']

// Remediation M2 R2-15/R2-16.
it('labels a paused batch and explains why', () => {
  render(<BatchStatus status="paused"/>)
  expect(screen.getByText('已暂停')).toBeVisible()
})

it('shows the pause reason and lets a person continue or stop the batch', () => {
  const onResume = vi.fn(), onStop = vi.fn()
  render(<BatchDetail detail={paused} onBack={() => undefined} onResume={onResume} onStop={onStop}/>)
  expect(screen.getByRole('status')).toHaveTextContent('连续 5 个任务在开始前因环境或代理问题失败，已暂停批次')
  expect(screen.getByRole('status')).toHaveTextContent('修复后可以继续')
  fireEvent.click(screen.getByRole('button', { name: '继续批次' }))
  expect(onResume).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: '停止批次' })).toBeEnabled()
})

it('offers no continue action unless the batch is paused', () => {
  const running = { ...paused, batch: { ...paused.batch, status: 'running', selectionOutcome: null } } as unknown as BatchDetailProps['detail']
  render(<BatchDetail detail={running} onBack={() => undefined} onResume={() => undefined}/>)
  expect(screen.queryByRole('button', { name: '继续批次' })).toBeNull()
})
