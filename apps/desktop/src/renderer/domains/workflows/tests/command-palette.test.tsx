import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CommandPalette } from '../components/CommandPalette'
import type { StudioCommand } from '../lib/studioCommands'

afterEach(cleanup)

const make = (over: Partial<StudioCommand> & { id: string; label: string }): StudioCommand =>
  ({ keywords: '', disabled: false, run: vi.fn(), ...over })

function setup(commands: StudioCommand[]) {
  const onOpenChange = vi.fn()
  render(<CommandPalette open onOpenChange={onOpenChange} commands={commands} />)
  return { onOpenChange, input: screen.getByRole('combobox') }
}

it('renders a labelled combobox controlling a listbox of options', () => {
  const { input } = setup([make({ id: 'a', label: '保存' }), make({ id: 'b', label: '打开' })])
  expect(screen.getByRole('dialog', { name: '命令面板' })).toBeTruthy()
  const list = screen.getByRole('listbox')
  expect(input.getAttribute('aria-controls')).toBe(list.id)
  expect(input.getAttribute('aria-expanded')).toBe('true')
  expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual(['保存', '打开'])
  expect(document.activeElement).toBe(input)
})

it('filters while typing and shows an empty hint', () => {
  const { input } = setup([make({ id: 'a', label: '保存' }), make({ id: 'b', label: '打开' })])
  fireEvent.change(input, { target: { value: '打' } })
  expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual(['打开'])
  fireEvent.change(input, { target: { value: 'xyz' } })
  expect(screen.queryAllByRole('option')).toEqual([])
  expect(screen.getByText('没有匹配的命令')).toBeTruthy()
})

it('moves the active option with arrows (skipping disabled) and runs it on Enter, closing first', () => {
  const run = vi.fn()
  const { input, onOpenChange } = setup([
    make({ id: 'a', label: '保存' }),
    make({ id: 'b', label: '新建', disabled: true }),
    make({ id: 'c', label: '打开', run }),
  ])
  const active = () => input.getAttribute('aria-activedescendant')
  const options = screen.getAllByRole('option')
  expect(active()).toBe(options[0].id)
  expect(options[0].getAttribute('aria-selected')).toBe('true')
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(active()).toBe(options[2].id)
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(active()).toBe(options[0].id)
  fireEvent.keyDown(input, { key: 'ArrowUp' })
  expect(active()).toBe(options[2].id)
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(onOpenChange).toHaveBeenCalledWith(false)
  expect(run).toHaveBeenCalledTimes(1)
})

it('exposes disabled options and never runs them', () => {
  const run = vi.fn()
  const { onOpenChange } = setup([make({ id: 'a', label: '新建', disabled: true, run })])
  const option = screen.getByRole('option', { name: '新建' })
  expect(option.getAttribute('aria-disabled')).toBe('true')
  fireEvent.click(option)
  expect(run).not.toHaveBeenCalled()
  expect(onOpenChange).not.toHaveBeenCalled()
})

it('runs an option on click and closes on Escape', () => {
  const run = vi.fn()
  const { onOpenChange } = setup([make({ id: 'a', label: '保存', run })])
  fireEvent.click(screen.getByRole('option', { name: '保存' }))
  expect(run).toHaveBeenCalledTimes(1)
  expect(onOpenChange).toHaveBeenCalledWith(false)
  onOpenChange.mockClear()
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  expect(onOpenChange).toHaveBeenCalledWith(false)
})

it('resets the query when reopened', () => {
  const commands = [make({ id: 'a', label: '保存' }), make({ id: 'b', label: '打开' })]
  const { rerender } = render(<CommandPalette open onOpenChange={() => {}} commands={commands} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '打' } })
  rerender(<CommandPalette open={false} onOpenChange={() => {}} commands={commands} />)
  rerender(<CommandPalette open onOpenChange={() => {}} commands={commands} />)
  expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('')
  expect(screen.getAllByRole('option')).toHaveLength(2)
})
