import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { moduleCategories } from '../lib/moduleCatalog'
import { useWorkflowStore } from '../editor-store'
beforeEach(() => { useWorkflowStore.getState().clearWorkflow() })
afterEach(cleanup)
it.each(moduleCategories.flatMap(category => category.modules))('NODE.%s.panel-registration: mounts the actual selected configuration', type => {
  useWorkflowStore.getState().addNode(type, { x: 120, y: 240 })
  const node = useWorkflowStore.getState().nodes.find(candidate => candidate.data.moduleType === type)!
  render(<ConfigPanel selectedNodeId={node.id} />)
  expect(screen.getByText(type, { exact: true })).toBeDefined()
  expect(screen.queryByText('选择一个节点查看配置', { exact: true })).toBeNull()
  expect(screen.queryByText('此节点已排除，保留原配置，仅供查看和导出', { exact: true })).toBeNull()
})
