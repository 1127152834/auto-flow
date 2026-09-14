import { createRef } from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from './table'
import { TableToolbar } from './table-toolbar'
afterEach(cleanup)

describe('shared table composition', () => {
  it('preserves native table structure, typed headers and caller refs', () => {
    const ref = createRef<HTMLTableElement>()
    render(<TableScroll label="资料列表"><Table ref={ref} aria-label="资料">
      <TableHeader><TableRow><TableHead>名称</TableHead><TableHead>值</TableHead></TableRow></TableHeader>
      <TableBody><TableRow aria-selected data-state="selected"><TableHead scope="row">温室</TableHead><TableCell>0</TableCell></TableRow></TableBody>
    </Table></TableScroll>)
    expect(ref.current).toBe(screen.getByRole('table', { name: '资料' }))
    expect(screen.getByRole('columnheader', { name: '名称' })).toHaveAttribute('scope', 'col')
    expect(screen.getByRole('rowheader', { name: '温室' })).toHaveAttribute('scope', 'row')
    expect(screen.getByRole('region', { name: '资料列表' })).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('row', { name: '温室 0' })).toHaveAttribute('aria-selected', 'true')
  })
  it('keeps a toolbar group and independent semantic search form without changing events', () => {
    render(<TableToolbar label="查询工具"><form role="search"><input aria-label="搜索" /></form><button disabled>导出</button></TableToolbar>)
    expect(screen.getByRole('group', { name: '查询工具' })).toContainElement(screen.getByRole('search'))
    expect(screen.getByRole('button', { name: '导出' })).toBeDisabled()
    expect(screen.queryByRole('toolbar')).toBeNull()
  })
  it('allows responsive consumers to choose grid layout and scroll axes', () => {
    render(<TableToolbar label="查询" className="grid sm:grid-cols-2"><TableScroll label="内嵌" className="overflow-x-auto overflow-y-hidden">资料</TableScroll></TableToolbar>)
    expect(screen.getByRole('group')).toHaveClass('grid', 'sm:grid-cols-2')
    expect(screen.getByRole('group')).not.toHaveClass('flex')
    expect(screen.getByRole('region')).toHaveClass('overflow-y-hidden')
  })
})
