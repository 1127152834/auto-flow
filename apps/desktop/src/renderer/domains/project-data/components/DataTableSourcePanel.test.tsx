import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
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
