import { act, cleanup, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { Node, NodeChange } from '@xyflow/react'
import type { WorkflowContent } from '../types'

type FlowProps = { nodes: Node[]; onNodesChange(changes: NodeChange[]): void }
const flow = vi.hoisted(() => ({ props: {} as FlowProps }))
vi.mock('@xyflow/react', () => ({
  ReactFlow: (props: FlowProps) => { flow.props = props; return null },
  Background: () => null, Controls: () => null, Handle: () => null,
  BackgroundVariant: { Dots: 'dots' }, Position: { Left: 'left', Right: 'right' },
}))
import { WorkflowCanvas } from '../components/WorkflowCanvas'
afterEach(cleanup)
it('retains measured dimensions when run markers change, including locked canvas updates', () => {
  const content: WorkflowContent = { document: { id: 'flow', name: 'flow', schemaVersion: 1, nodes: [{ id: 'node', type: 'android_manual', label: 'manual', config: {} }], edges: [], variables: [] }, layout: { nodes: { node: { x: 0, y: 0 } }, viewport: { x: 0, y: 0, zoom: 1 } } }
  const props = { content, catalog: [], issues: [], selectedNodes: [], selectedEdges: [], disabled: true, onSelect: vi.fn(), onMove: vi.fn(), onViewport: vi.fn(), onConnect: vi.fn(), onAdd: vi.fn(), onEditStart: vi.fn(), onEditEnd: vi.fn(), onPointer: vi.fn() }
  const view = render(<WorkflowCanvas {...props} runMarkers={{ node: '等待人工' }} />)
  act(() => flow.props.onNodesChange([{ id: 'node', type: 'dimensions', dimensions: { width: 220, height: 104 } }]))
  view.rerender(<WorkflowCanvas {...props} runMarkers={{ node: '已完成' }} />)
  expect(flow.props.nodes[0].measured).toEqual({ width: 220, height: 104 })
  expect(props.onMove).not.toHaveBeenCalled()
})
