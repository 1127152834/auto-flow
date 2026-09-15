import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

Element.prototype.scrollIntoView = vi.fn()
Element.prototype.hasPointerCapture = vi.fn(() => false)
Element.prototype.setPointerCapture = vi.fn()
Element.prototype.releasePointerCapture = vi.fn()

const cases = [
  { type: 'ai_generate_image', field: 'provider', before: 'openai', label: 'AI提供商', option: 'Stability AI', after: 'stability' },
  { type: 'ai_generate_video', field: 'provider', before: 'runway', label: 'AI提供商', option: '自定义API', after: 'custom' },
  { type: 'webhook_request', field: 'method', before: 'POST', label: '请求方法', option: 'GET', after: 'GET' },
] as const

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

it.each(cases)('NODE.$type $field uses the complete Select composite and persists the choice', ({ type, field, before, label, option, after }) => {
  store.getState().addNode(type as ModuleType, { x: 0, y: 0 }, { [field]: before })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)

  const control = within(screen.getByText(label).parentElement!).getByRole('combobox')
  fireEvent.keyDown(control, { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: option }))
  expect(store.getState().nodes[0].data[field]).toBe(after)

  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(before)
  act(() => store.getState().redo())
  expect(store.getState().nodes[0].data[field]).toBe(after)

  const document = store.getState().exportWorkflow()
  act(() => {
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(document)).toBe(true)
  })
  expect(store.getState().nodes.find(node => node.id === id)?.data[field]).toBe(after)
})
