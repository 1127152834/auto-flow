import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
import { useWorkflowStore } from '../editor-store'
import { LogPanel } from '../components/LogPanel'
beforeEach(() => { useWorkflowStore.getState().clearWorkflow(); useWorkflowStore.getState().setBottomPanelTab('variables') })
afterEach(cleanup)
Element.prototype.scrollIntoView = vi.fn()
it.each([
  ['number', '0', '12no'], ['number', '0', 'Infinity'],
  ['array', '[]', '{broken'], ['array', '[]', '{}'],
  ['object', '{}', '[]'], ['object', '{}', 'null'],
])('rejects invalid %s value %s/%s without replacing it with fake defaults', (type, placeholder, value) => {
  render(<LogPanel />)
  fireEvent.click(screen.getByRole('button', { name: '添加变量' }))
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'test_value' } })
  fireEvent.keyDown(screen.getByRole('combobox', { name: '变量类型' }), { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: ({ number: '数字', array: '列表', object: '字典' } as Record<string, string>)[type] }))
  fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value } })
  fireEvent.click(screen.getByRole('button', { name: '确认添加变量' }))
  expect(screen.getByRole('alert').textContent).not.toBe('')
  expect(useWorkflowStore.getState().variables).toEqual([])
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false)
  expect((screen.getByPlaceholderText(placeholder) as HTMLInputElement).value).toBe(value)
})
it('creates a value through the panel and restores it with document history', () => {
  render(<LogPanel />)
  fireEvent.click(screen.getByRole('button', { name: '添加变量' }))
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'title' } })
  fireEvent.change(screen.getByPlaceholderText('值'), { target: { value: 'hello' } })
  fireEvent.click(screen.getByRole('button', { name: '确认添加变量' }))
  expect(screen.getByRole('cell', { name: 'hello' })).toBeDefined()
  act(() => useWorkflowStore.getState().undo())
  expect(screen.getByText('暂无全局变量')).toBeDefined()
  act(() => useWorkflowStore.getState().redo())
  expect(screen.getByRole('cell', { name: 'hello' })).toBeDefined()
})
