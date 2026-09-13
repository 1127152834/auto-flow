import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { RecordDetailPage } from './RecordDetailPage'
import { RecordEditPage } from './RecordEditPage'
afterEach(cleanup)
it('renders detail as a page with one main heading and separate real actions', async () => {
  const edit = vi.fn(), remove = vi.fn(), back = vi.fn()
  render(<RecordDetailPage title="温室管理清单" fieldsView={<p>真实字段值</p>} statusForm={<p>业务状态控件</p>} createdAt="2026-09-13T00:00:00Z" updatedAt="2026-09-13T01:00:00Z" onBack={back} onEdit={edit} onDelete={remove} />)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '编辑记录' })); expect(edit).toHaveBeenCalledOnce()
  await user.click(screen.getByRole('button', { name: '删除记录' })); expect(remove).toHaveBeenCalledOnce()
  await user.click(screen.getByRole('button', { name: '返回记录列表' })); expect(back).toHaveBeenCalledOnce()
})
it('keeps archived actions disabled and exposes a retryable read failure', () => {
  const props = { title: '记录详情', onBack: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn(), readonly: true }
  const view = render(<RecordDetailPage {...props} fieldsView={<p>字段值</p>} />)
  expect(screen.getByRole('button', { name: '编辑记录' })).toBeDisabled()
  view.rerender(<RecordDetailPage {...props} error="记录已失效" onRetry={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('记录已失效')
  expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
})
it('create and edit pages compose one shared form without a modal or automatic status editing', () => {
  const props = { onBack: vi.fn(), editorForm: <form aria-label="真实记录表单"><input aria-label="标题" /></form> }
  const view = render(<RecordEditPage {...props} mode="create" />)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('新增记录')
  expect(screen.getByText('业务状态在记录详情中单独维护。')).toBeVisible()
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  view.rerender(<RecordEditPage {...props} mode="edit" />)
  expect(screen.getByRole('form',{name:'真实记录表单'})).toBeVisible()
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  expect(screen.getByText('业务状态在记录详情中单独维护。')).toBeVisible()
})
