import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { ExecutionSemanticsBanner } from '../components/ExecutionSemanticsBanner'
import { useWorkflowStore as store } from '../editor-store'

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

const legacyDocument = {
  id: 'legacy', name: '旧流程',
  nodes: [
    { id: 'a', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击', selector: '#a' } },
    { id: 'b', type: 'moduleNode', position: { x: 0, y: 100 }, data: { moduleType: 'close_page', label: '关闭' } },
  ],
  edges: [{ id: 'e', source: 'a', target: 'b', sourceHandle: 'error' }],
  variables: [],
}

it('new workflows are saved with the v2 error semantics', () => {
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBe('autoflow-v2')
})

it('imported documents keep their semantics and legacy ones with error edges offer an upgrade', () => {
  act(() => { expect(store.getState().importWorkflow(legacyDocument)).toBe(true) })
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBeUndefined()
  render(<ExecutionSemanticsBanner />)
  fireEvent.click(screen.getByRole('button', { name: '改用新规则' }))
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBe('autoflow-v2')
  expect(screen.queryByRole('status')).toBeNull()
})

it('legacy documents without error edges show no banner', () => {
  act(() => { store.getState().importWorkflow({ ...legacyDocument, edges: [{ id: 'e', source: 'a', target: 'b' }] }) })
  render(<ExecutionSemanticsBanner />)
  expect(screen.queryByRole('status')).toBeNull()
})

it('an imported v2 document stays v2 and an unknown marker is treated as the legacy rule', () => {
  act(() => { store.getState().importWorkflow({ ...legacyDocument, executionSemantics: 'autoflow-v2' }) })
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBe('autoflow-v2')
  render(<ExecutionSemanticsBanner />)
  expect(screen.queryByRole('status')).toBeNull()
  act(() => { store.getState().importWorkflow({ ...legacyDocument, executionSemantics: 'future-v9' }) })
  expect(JSON.parse(store.getState().exportWorkflow()).executionSemantics).toBeUndefined()
})

it('upgrading is idempotent and does not dirty an already upgraded document', () => {
  act(() => { store.getState().clearWorkflow() })
  act(() => { store.getState().upgradeExecutionSemantics() })
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
