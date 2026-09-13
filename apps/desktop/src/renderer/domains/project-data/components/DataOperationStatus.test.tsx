import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { DataOperationStatus } from './DataOperationStatus'

afterEach(cleanup)
type Operation = components['schemas']['ProjectOperationView']
const operation = (status: Operation['status'], result: unknown = null) => ({ operationId: 'operation', kind: 'setRecordStatuses', status, result, error: null } as Operation)
describe('data operation status', () => {
  it('does not show success for an accepted operation', () => {
    render(<DataOperationStatus operation={operation('accepted')} />)
    expect(screen.getByRole('status')).toHaveTextContent('已接受，等待处理')
    expect(screen.queryByText('操作已完成')).not.toBeInTheDocument()
  })
  it('shows partial cancellation evidence separately from complete success', () => {
    render(<DataOperationStatus operation={operation('failed', { blocks: [], changedCount: 4, conflictCount: 2, notStartedCount: 3, cancelled: true })} />)
    expect(screen.getByRole('status')).toHaveTextContent('后续处理已停止')
    expect(screen.getByText('已修改 4 条')).toBeInTheDocument()
    expect(screen.getByText('冲突 2 条')).toBeInTheDocument()
    expect(screen.getByText('未执行 3 条')).toBeInTheDocument()
    expect(screen.queryByText('操作已完成')).not.toBeInTheDocument()
  })
  it('shows the real exported file only for a succeeded result', () => {
    render(<DataOperationStatus operation={operation('succeeded', { filename: '资料.xlsx', saved: true, recordCount: 8 })} />)
    expect(screen.getByRole('status')).toHaveTextContent('操作已完成')
    expect(screen.getByText('资料.xlsx · 8 条记录')).toBeInTheDocument()
  })
})
