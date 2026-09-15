import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ExcelInspectionPanel } from './ExcelInspectionPanel'

const inspection = { inspectionId: 'i', fingerprint: 'f', filename: '客户.xlsx', expiresAt: '2026-09-13T12:05:00Z', issues: ['工作簿提示'], sheets: [{ sheetId: 's1', name: '客户', headers: ['姓名', '编号'], sample: [['张三', '001']], rowCount: 20, ignoredEmptyRowCount: 2, formulaRowCount: [3], identityCandidates: [1], issues: ['存在公式'] }] }
afterEach(cleanup)
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});HTMLElement.prototype.hasPointerCapture=vi.fn(()=>false);HTMLElement.prototype.setPointerCapture=vi.fn();HTMLElement.prototype.releasePointerCapture=vi.fn();HTMLElement.prototype.scrollIntoView=vi.fn()})

it('shows bounded inspection evidence and continues with the selected sheet', async () => {
  const select = vi.fn(), next = vi.fn()
  render(<ExcelInspectionPanel inspection={inspection as never} selectedSheetId="s1" onChoose={vi.fn()} onSelectSheet={select} onContinue={next} now={() => new Date('2026-09-13T12:00:00Z')} />)
  expect(screen.getByText('客户.xlsx')).not.toBeNull()
  expect(screen.getByText(/20 条数据/)).not.toBeNull()
  expect(screen.getByText(/忽略 2 个空行/)).not.toBeNull()
  expect(screen.getByText('存在公式')).not.toBeNull()
  expect(screen.getByText(/第 1 列 3 行/)).not.toBeNull()
  expect(screen.getByText(/第 2 列可作为候选身份/)).not.toBeNull()
  expect(screen.getByRole('table').textContent).toContain('张三')
  await userEvent.click(screen.getByRole('button', { name: '继续字段映射' }))
  expect(next).toHaveBeenCalledWith(inspection.sheets[0])
})

it('shows choosing, checking and expiration states without continuing stale inspection', () => {
  const choose = vi.fn()
  const view = render(<ExcelInspectionPanel inspection={null} selectedSheetId={null} checking onChoose={choose} onSelectSheet={vi.fn()} onContinue={vi.fn()} />)
  expect(screen.getByText('正在检查工作簿…')).not.toBeNull()
  view.rerender(<ExcelInspectionPanel inspection={inspection as never} selectedSheetId="s1" onChoose={choose} onSelectSheet={vi.fn()} onContinue={vi.fn()} now={() => new Date('2026-09-13T12:06:00Z')} />)
  expect(screen.getByText(/检查结果已过期/)).not.toBeNull()
  expect((screen.getByRole('button', { name: '继续字段映射' }) as HTMLButtonElement).disabled).toBe(true)
})
it('shows a semantic option for a stale sheet without exposing its UUID', async () => {
  const sheetId='11111111-2222-4333-8444-555555555555'
  render(<ExcelInspectionPanel inspection={inspection as never} selectedSheetId={sheetId} onChoose={vi.fn()} onSelectSheet={vi.fn()} onContinue={vi.fn()} now={() => new Date('2026-09-13T12:00:00Z')} />)
  const select=screen.getByRole('combobox',{name:'工作表'});expect(select.textContent).toContain('工作表暂不可用');await userEvent.click(select);expect(screen.getByRole('option',{name:'工作表暂不可用'})).not.toBeNull()
  expect(document.body.textContent).not.toContain(sheetId);for(const element of document.querySelectorAll('[title],[placeholder],[aria-label],[aria-description]')) for(const name of ['title','placeholder','aria-label','aria-description']) expect(element.getAttribute(name)??'').not.toContain(sheetId)
})
