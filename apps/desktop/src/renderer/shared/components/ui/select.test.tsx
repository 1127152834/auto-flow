import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { Select } from './select'
import { decodeValue, encodeValue } from './choice-types'
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  Element.prototype.scrollIntoView = vi.fn()
  Element.prototype.hasPointerCapture = () => false
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('maps null independently of empty strings and prefixed/custom resource keys', () => {
  const values = [null, '', 'v:x', '__custom__', '中文', 'licensed:146']
  expect(new Set(values.map(encodeValue)).size).toBe(values.length)
  for (const value of values) expect(decodeValue(encodeValue(value))).toBe(value)
})
it('renders a real trigger, opens a custom listbox and selects an empty-string option', async () => {
  const user = userEvent.setup(), change = vi.fn(), ref = createRef<HTMLButtonElement>()
  render(<Select aria-label="通道" ref={ref} value={null} onValueChange={change} options={[{ value: '', label: '跟随浏览器' }, { value: 'v:x', label: '指定通道' }]} />)
  const trigger = screen.getByRole('combobox', { name: '通道' })
  expect(ref.current).toBe(trigger)
  trigger.focus(); await user.keyboard('{Enter}')
  expect(screen.getByRole('listbox')).toBeVisible()
  await user.click(screen.getByRole('option', { name: '跟随浏览器' }))
  expect(change).toHaveBeenCalledWith('')
})
it('retains unavailable values and read-only selection without opening a popup', async () => {
  const user = userEvent.setup(), change = vi.fn()
  render(<Select aria-label="内核" value="missing:146" readOnly onValueChange={change} options={[]} />)
  const trigger = screen.getByRole('combobox', { name: '内核' })
  expect(trigger).toHaveTextContent('missing:146')
  await user.click(trigger)
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(change).not.toHaveBeenCalled()
})
it('identifies an unavailable selection without replacing it', () => {
  render(<Select aria-label="内核" value="missing" options={[]} onValueChange={vi.fn()} readOnly />)
  expect(screen.getByRole('combobox')).toHaveAccessibleDescription('当前选项不可用，请重新选择')
})
it('does not change read-only values through Radix typeahead', async () => {
  const user = userEvent.setup(), change = vi.fn()
  render(<Select aria-label="只读" value="a" options={[{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }]} onValueChange={change} readOnly />)
  await user.tab(); await user.keyboard('b')
  expect(change).not.toHaveBeenCalled()
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})
it('does not offer null clearing for a required enum',()=>{
 render(<Select aria-label="协议" value="socks5" clearable={false} options={[{value:'socks5',label:'SOCKS5'}]} onValueChange={vi.fn()}/>)
 expect(screen.queryByRole('button',{name:'清除选择'})).not.toBeInTheDocument()
})
