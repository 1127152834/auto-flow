import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef, useState } from 'react'
import { Autocomplete, Combobox } from './combobox'
import type { ChoiceOption } from './choice-types'

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const options: ChoiceOption[] = [{ value: '', label: '跟随系统' }, { value: 'a', label: '同名', description: '公开版', keywords: ['public'] }, { value: 'b', label: '同名', description: '正式版' }, { value: 'c', label: '不可用', disabled: true }]
it('keeps search drafts separate from selected values and restores the label on Escape/blur', async () => {
  const user = userEvent.setup(), change = vi.fn(), ref = createRef<HTMLInputElement>(), blur = vi.fn()
  render(<Combobox aria-label="资源" ref={ref} value="a" onValueChange={change} onBlur={blur} options={options} />)
  const input = screen.getByRole('combobox', { name: '资源' })
  expect(ref.current).toBe(input)
  expect(input).toHaveValue('同名')
  await user.clear(input); await user.type(input, 'public')
  expect(change).not.toHaveBeenCalled()
  expect(screen.getAllByRole('option')).toHaveLength(1)
  await user.keyboard('{Escape}')
  expect(input).toHaveValue('同名')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  await user.tab()
  expect(blur).toHaveBeenCalled()
})
it('commits duplicate labels by value and explicitly clears to null', async () => {
  const user = userEvent.setup(), change = vi.fn()
  function Example() { const [value, setValue] = useState<string | null>('a'); return <Combobox aria-label="资源" value={value} onValueChange={next => { setValue(next); change(next) }} options={options} /> }
  render(<Example />)
  const input = screen.getByRole('combobox', { name: '资源' })
  await user.clear(input); await user.type(input, 'b')
  await user.click(screen.getByRole('option', { name: /正式版/ }))
  expect(change).toHaveBeenLastCalledWith('b')
  await user.click(screen.getByRole('button', { name: '清除选择' }))
  expect(change).toHaveBeenLastCalledWith(null)
  expect(input).toHaveFocus()
})
it('filters 500 options by value, keeps disabled items unselectable and exposes retry', async () => {
  const user = userEvent.setup(), change = vi.fn(), retry = vi.fn()
  const many = Array.from({ length: 500 }, (_, i) => ({ value: `key-${i}`, label: `选项 ${i}` }))
  function Example() { const [value, setValue] = useState<string | null>(null); return <Combobox aria-label="目录" value={value} onValueChange={v => { setValue(v); change(v) }} options={[...many, ...options]} errorMessage="目录暂不可用" onRetry={retry} /> }
  render(<Example />)
  const input = screen.getByRole('combobox', { name: '目录' })
  expect(input).toHaveAccessibleDescription('目录暂不可用')
  await user.type(input, 'key-499')
  expect(screen.getAllByRole('option')).toHaveLength(1)
  await user.click(screen.getByRole('option', { name: '选项 499' }))
  expect(change).toHaveBeenLastCalledWith('key-499')
  await user.click(screen.getByRole('button', { name: '重试加载' }))
  expect(retry).toHaveBeenCalledOnce()
})
it('never silently substitutes an unavailable current value', () => {
  const change = vi.fn()
  render(<Combobox aria-label="失效内核" value="missing" onValueChange={change} options={options} readOnly />)
  expect(screen.getByRole('combobox')).toHaveValue('missing')
  expect(screen.getByRole('combobox')).toHaveAttribute('readonly')
  expect(change).not.toHaveBeenCalled()
})
it('supports free text and composition without submitting Enter to the form', async () => {
  const user = userEvent.setup(), submitted = vi.fn(e => e.preventDefault()), selected = vi.fn()
  function Example() { const [value, setValue] = useState(''); return <form onSubmit={submitted}><Autocomplete aria-label="自定义 UA" value={value} onValueChange={setValue} options={options} onOptionSelect={selected} /></form> }
  render(<Example />)
  const input = screen.getByRole('combobox', { name: '自定义 UA' })
  await user.type(input, 'custom-agent')
  expect(input).toHaveValue('custom-agent')
  fireEvent.compositionStart(input)
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', isComposing: true })
  expect(submitted).not.toHaveBeenCalled(); expect(selected).not.toHaveBeenCalled()
  fireEvent.compositionEnd(input)
})
it('clears a selected empty-string option without confusing it with null', async () => {
  const user = userEvent.setup(), change = vi.fn()
  render(<Combobox aria-label="空值" options={options} value="" onValueChange={change} />)
  expect(screen.getByRole('combobox')).toHaveValue('跟随系统')
  await user.click(screen.getByRole('button', { name: '清除选择' }))
  expect(change).toHaveBeenCalledWith(null)
})
it('filters free input and commits the option value independently from its label', async () => {
  const user = userEvent.setup(), selected = vi.fn()
  function Example() { const [value, setValue] = useState(''); return <><Autocomplete aria-label="自由值" options={options} value={value} onValueChange={setValue} onOptionSelect={selected} /><button>外部按钮</button></> }
  render(<Example />)
  const input = screen.getByRole('combobox')
  await user.type(input, 'public')
  expect(screen.getAllByRole('option')).toHaveLength(1)
  await user.click(screen.getByRole('option', { name: /公开版/ }))
  expect(input).toHaveValue('a'); expect(selected).toHaveBeenCalledExactlyOnceWith(options[1])
  await user.click(screen.getByRole('button', { name: '外部按钮' }))
  expect(input).toHaveValue('a'); expect(selected).toHaveBeenCalledTimes(1)
})
it('does not commit disabled options or drafts and preserves raw form values', async () => {
  const user = userEvent.setup(), change = vi.fn()
  render(<form aria-label="控件表单"><Combobox name="kernel" aria-label="内核" options={options} value="a" onValueChange={change} /><button>完成</button></form>)
  const input = screen.getByRole('combobox')
  await user.clear(input); await user.type(input, '不可用')
  const disabled = screen.getByRole('option', { name: '不可用' })
  expect(disabled).toHaveAttribute('aria-disabled', 'true')
  await user.click(disabled); expect(change).not.toHaveBeenCalled()
  await user.keyboard('{Escape}')
  expect(input).toHaveValue('同名')
  await user.clear(input); await user.type(input, '没有匹配')
  await user.tab()
  expect(input).toHaveValue('同名'); expect(change).not.toHaveBeenCalled()
  expect(new FormData(screen.getByRole('form') as HTMLFormElement).get('kernel')).toBe('a')
})
it('announces unavailable selections even when read-only prevents opening', () => {
  render(<Combobox aria-label="失效选择" value="missing" options={options} onValueChange={vi.fn()} readOnly />)
  expect(screen.getByRole('combobox')).toHaveAccessibleDescription('当前选项不可用，请重新选择')
})

it('keeps the popup closed after Escape restores a label excluded by the filter', async () => {
  const user = userEvent.setup()
  render(<Combobox aria-label="严格选择" options={options} value="a" onValueChange={vi.fn()} />)
  const input = screen.getByRole('combobox')
  await user.clear(input); await user.type(input, '不存在')
  await user.keyboard('{Escape}')
  expect(input).toHaveValue('同名')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  await user.clear(input); await user.type(input, 'public')
  expect(screen.getByRole('listbox')).toBeInTheDocument()
})
