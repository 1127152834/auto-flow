import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DataTableSourcePanel } from './DataTableSourcePanel'

afterEach(cleanup)
it('shows only saved Excel source facts and explains snapshot behavior', () => {
  render(<DataTableSourcePanel table={{ sourceKind: 'excel', source: { kind: 'excel', filename: '客户.xlsx', sheetName: '客户', importedAt: '2026-09-13T02:00:00Z' } } as never} />)
  expect(screen.getByText('客户.xlsx')).toBeVisible(); expect(screen.getByText('客户')).toBeVisible(); expect(screen.getByText(/本地副本/)).toBeVisible()
  expect(screen.getByText(/不会监听原文件，也不会回写/)).toBeVisible(); expect(screen.queryByText(/fingerprint|tableId|路径/i)).toBeNull()
  expect(screen.getByRole('time')).toHaveAttribute('datetime', '2026-09-13T02:00:00Z')
})

it('describes local maintenance without inventing a file or sync count', () => {
  render(<DataTableSourcePanel table={{ sourceKind: 'local', source: { kind: 'local', filename: null, sheetName: null, importedAt: null } } as never} />)
  expect(screen.getByText('手动维护')).toBeVisible(); expect(screen.getByText(/直接在项目中维护/)).toBeVisible()
  expect(screen.queryByText(/同步|0 条/)).toBeNull()
})

it('states when legacy source metadata has not been saved', () => {
  render(<DataTableSourcePanel table={{ sourceKind: 'excel', source: null } as never} />)
  expect(screen.getByText('Excel 文件')).toBeVisible(); expect(screen.getByText(/没有已保存的文件信息/)).toBeVisible()
})


it('renders the source fact table with real zero records and guarded reimport entry points', () => {
  const onReimport = vi.fn()
  const table = { sourceKind: 'excel' as const, recordCount: 0, source: { kind: 'excel' as const, filename: '客户.xlsx', importedAt: 'invalid-date' } }
  const view = render(<DataTableSourcePanel table={table} onReimport={onReimport} />)
  expect(screen.getByRole('table', { name: '来源事实' })).toBeVisible()
  expect(screen.getByText('0 条')).toBeVisible()
  expect(screen.getByText('导入时间无法读取')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '更换文件' }))
  fireEvent.click(screen.getByRole('button', { name: '重新导入…' }))
  expect(onReimport).toHaveBeenCalledTimes(2)
  expect(screen.getByText(/先预览影响，再确认替换/)).toBeVisible()
  view.rerender(<DataTableSourcePanel table={table} onReimport={onReimport} readonly />)
  expect(screen.getByRole('button', { name: '重新导入…' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '更换文件' }))
  expect(onReimport).toHaveBeenCalledTimes(2)
})

it('does not expose source file paths or invent a missing count', () => {
  render(<DataTableSourcePanel table={{ sourceKind: 'excel', source: { kind: 'excel', filename: 'C:\\private\\客户.xlsx' } }} />)
  expect(screen.getByText('客户.xlsx')).toBeVisible()
  expect(screen.queryByText(/private/)).toBeNull()
  expect(screen.queryByText('0 条')).toBeNull()
  expect(screen.queryByRole('button')).toBeNull()
})

it('disables existing reimport actions during external locks without fabricating Sheets sync', () => {
  const onReimport = vi.fn()
  const view = render(<DataTableSourcePanel table={{ sourceKind: 'excel', source: null }} onReimport={onReimport} disabled />)
  expect(screen.getByRole('button', { name: '更换文件' })).toBeDisabled()
  view.rerender(<DataTableSourcePanel table={{ sourceKind: 'sheets', source: null }} onReimport={onReimport} />)
  expect(screen.getByText('Google Sheets')).toBeVisible()
  expect(screen.queryByRole('button')).toBeNull()
  expect(screen.queryByText(/同步成功|0 条/)).toBeNull()
})

it('omits an empty facts table when an unconfigured source has no facts', () => {
  render(<DataTableSourcePanel table={{ sourceKind: 'unconfigured', source: null }} />)
  expect(screen.getByText('尚未配置')).toBeVisible()
  expect(screen.queryByRole('table')).toBeNull()
})
