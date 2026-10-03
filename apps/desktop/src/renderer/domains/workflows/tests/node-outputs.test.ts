import { expect, it } from 'vitest'
import { outputAvailability } from '../lib/nodeOutputs'

// Remediation M2 R2-29 / AC2-17.
const node = (id: string, moduleType: string, extra: Record<string, unknown> = {}) => ({ id, data: { moduleType, label: id, ...extra } })
const edge = (source: string, target: string, sourceHandle?: string) => ({ source, target, sourceHandle })
const summary = (items: ReturnType<typeof outputAvailability>) => Object.fromEntries(items.map(item => [`${item.nodeId}.${item.key}`, item.required]))

it('an output on every path is required; one branch of a merge is conditional', () => {
  const nodes = [node('first', 'set_variable', { variableName: 'a' }), node('check', 'condition'), node('yes', 'set_variable', { variableName: 'b' }), node('no', 'set_variable', { variableName: 'c' }), node('merge', 'set_variable', { variableName: 'd' })]
  const edges = [edge('first', 'check'), edge('check', 'yes', 'true'), edge('check', 'no', 'false'), edge('yes', 'merge'), edge('no', 'merge')]
  expect(summary(outputAvailability(nodes, edges, 'merge'))).toEqual({ 'first.variableName': true, 'yes.variableName': false, 'no.variableName': false })
})

it('loop variables are required only inside the body; after a possibly empty loop everything from it is conditional', () => {
  const nodes = [node('each', 'foreach', { itemVariable: 'item', indexVariable: 'i' }), node('body', 'set_variable', { variableName: 'inside' }), node('after', 'set_variable', { variableName: 'out' })]
  const edges = [edge('each', 'body', 'loop'), edge('each', 'after', 'done')]
  expect(summary(outputAvailability(nodes, edges, 'body'))).toEqual({ 'each.itemVariable': true, 'each.indexVariable': true })
  expect(summary(outputAvailability(nodes, edges, 'after'))).toEqual({ 'each.itemVariable': false, 'each.indexVariable': false, 'body.variableName': false })
})

it('a failed node gives nothing to its error branch, and a rename keeps the stable reference', () => {
  const nodes = [node('risky', 'set_variable', { variableName: 'value' }), node('handle', 'set_variable', { variableName: 'h' }), node('next', 'set_variable', { variableName: 'n' })]
  const edges = [edge('risky', 'handle', 'error'), edge('risky', 'next')]
  expect(outputAvailability(nodes, edges, 'handle')).toEqual([])
  const [before] = outputAvailability(nodes, edges, 'next')
  const renamed = nodes.map(item => item.id === 'risky' ? node('risky', 'set_variable', { variableName: 'renamed', label: '新名字' }) : item)
  const [after] = outputAvailability(renamed, edges, 'next')
  expect([before.reference, after.reference]).toEqual(['node.risky.variableName', 'node.risky.variableName'])
  expect([before.variable, after.variable, after.label]).toEqual(['value', 'renamed', '新名字'])
  expect(after.required).toBe(true)
})

it('the picker offers earlier outputs by stable reference and names the source variable on insert', async () => {
  const React = await import('react')
  const { render, screen, fireEvent, cleanup } = await import('@testing-library/react')
  const { VariableInput } = await import('../components/controls/variable-input')
  const { useWorkflowStore } = await import('../editor-store')
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addNode('list_length', { x: 0, y: 0 })
  useWorkflowStore.getState().addNode('set_variable', { x: 0, y: 100 })
  const [source, target] = useWorkflowStore.getState().nodes
  useWorkflowStore.setState({ edges: [{ id: 'e', source: source.id, target: target.id }] as never, selectedNodeId: target.id })
  const changes: string[] = []
  function Controlled() {
    const [value, setValue] = React.useState('')
    return React.createElement(VariableInput, { value, onChange: (next: string) => { changes.push(next); setValue(next) } })
  }
  render(React.createElement(Controlled))
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: '{', selectionStart: 1 } })
  const [option] = await screen.findAllByText('「列表长度」的结果')
  expect(option.textContent).not.toContain(source.id)
  fireEvent.click(option)
  expect(changes.at(-1)).toBe(`{node.${source.id}.variableName}`)
  const named = useWorkflowStore.getState().nodes.find(item => item.id === source.id)!.data as Record<string, unknown>
  expect(named.variableName).toBe('list_length_variableName')
  cleanup()
})
