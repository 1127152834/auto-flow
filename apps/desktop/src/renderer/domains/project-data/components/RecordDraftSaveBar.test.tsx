import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RecordDraftSaveBar } from './RecordDraftSaveBar'
afterEach(cleanup)
it('distinguishes draft count, pending evidence and leaving the view from cancelling a write', () => {
 const onSave = vi.fn(), onDiscard = vi.fn(), onReconcile = vi.fn()
 const { rerender } = render(<RecordDraftSaveBar count={2} state="draft" onSave={onSave} onDiscard={onDiscard} onReconcile={onReconcile} />)
 fireEvent.click(screen.getByRole('button', { name: '保存 2 行' })); expect(onSave).toHaveBeenCalledOnce()
 rerender(<RecordDraftSaveBar count={2} state="uncertain" onSave={onSave} onDiscard={onDiscard} onReconcile={onReconcile} />)
 expect(screen.queryByRole('button', { name: '放弃新增' })).toBeNull()
 fireEvent.click(screen.getByRole('button', { name: '查询保存结果' })); expect(onReconcile).toHaveBeenCalledOnce()
 expect(screen.queryByText('已保存')).toBeNull()
})
