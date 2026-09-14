import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.mock('../hooks/useVirtualizer', () => ({
  useVirtualizer: ({ count, estimateSize }: { count: number; estimateSize: number }) => ({
    virtualItems: Array.from({ length: count }, (_, index) => ({ index, start: index * estimateSize, size: estimateSize })),
    totalSize: count * estimateSize,
    scrollToBottom: vi.fn(),
    scrollToTop: vi.fn(),
  }),
}))

import { DataTable } from '../components/DataTable'

afterEach(cleanup)

it('keeps the original row index when sorted rows are edited and deleted', () => {
  const onEdit = vi.fn()
  const onDeleteRow = vi.fn()
  render(<DataTable data={[{ score: 20 }, { score: 10 }]} columns={['score']} onEdit={onEdit} onDeleteRow={onDeleteRow} onDeleteColumn={vi.fn()} displayMode="head" />)

  fireEvent.click(screen.getByTitle('点击排序（升序 / 降序 / 取消）'))
  fireEvent.click(screen.getByText('10'))
  fireEvent.change(screen.getByDisplayValue('10'), { target: { value: '11' } })
  fireEvent.keyDown(screen.getByDisplayValue('11'), { key: 'Enter' })
  expect(onEdit).toHaveBeenCalledWith(1, 'score', '11')

  fireEvent.click(screen.getByRole('button', { name: '删除第 2 行' }))
  expect(onDeleteRow).toHaveBeenCalledWith(1)
  const region = screen.getByRole('region')
  expect(region.getAttribute('aria-label')).toBe('数据预览')
  expect(region.tabIndex).toBe(0)
  expect(region.classList.contains('af-studio-grid-body')).toBe(true)
  region.scrollLeft = 80
  fireEvent.scroll(region)
  expect(region.parentElement?.querySelector<HTMLElement>('.af-studio-grid-header')?.style.transform).toBe('translateX(-80px)')
})
