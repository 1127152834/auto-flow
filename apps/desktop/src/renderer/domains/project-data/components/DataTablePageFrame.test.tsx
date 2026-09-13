import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { DataTablePageFrame } from './DataTablePageFrame'

afterEach(cleanup)

it('keeps the table header, tabs, notice, and page content inside one surface', () => {
  render(<DataTablePageFrame
    header={<h2>新增记录</h2>}
    tabs={<nav aria-label="数据表功能">数据记录</nav>}
    notice={<div role="alert">云端推送失败</div>}
  ><form aria-label="记录表单" /></DataTablePageFrame>)

  const frame = screen.getByTestId('data-table-page-frame')
  expect(frame).toHaveAttribute('data-table-page-frame')
  expect(within(frame).getByRole('heading', { name: '新增记录' })).toBeVisible()
  expect(within(frame).getByRole('navigation', { name: '数据表功能' })).toBeVisible()
  expect(within(frame).getByRole('alert')).toBeVisible()
  expect(within(frame).getByRole('form', { name: '记录表单' })).toBeVisible()
  expect(frame.querySelector('[data-table-page-frame-header]')).toHaveClass('flex-wrap', 'min-w-0', 'items-start')
  expect(frame.querySelector('footer')).not.toBeInTheDocument()
})

it('renders an optional full-width footer after the page content', () => {
  render(<DataTablePageFrame header={<h2>资料库</h2>} tabs={<div>页签</div>} notice={null} footer={<button>保存到本地</button>}><div>字段</div></DataTablePageFrame>)

  const frame = screen.getByTestId('data-table-page-frame')
  const footer = within(frame).getByRole('contentinfo')
  expect(footer).toHaveClass('w-full', 'border-t')
  expect(within(footer).getByRole('button', { name: '保存到本地' })).toBeVisible()
  expect(frame.lastElementChild).toBe(footer)
})
