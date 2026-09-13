import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { addNode, connectNodes, createWorkflow, deleteSelection, pasteNodes, patchNode, renameLoopVariable, renameVariable, signature } from '../editor-model'
import { createHistory, editHistory, undoHistory } from '../history'
import { blockNodes } from '../control-model'
import { ControlFields } from '../components/ControlFields'
import { NodeCatalog } from '../components/NodeCatalog'
import type { NodeDefinition } from '../types'

const definition = (type: NodeDefinition['type'], config = {}): NodeDefinition => ({ type, title: type, description: '', category: '流程控制', defaultConfig: { timeoutSeconds: 60, ...config }, configSchema: {}, inputPorts: ['in'], outputPorts: [], runnable: true })

it('adds both empty branches with distinct ports, pairs identities on paste and undoes complete block deletion', () => {
  const original = addNode(createWorkflow(), definition('condition'), { x: 10, y: 20 })
  const [start, end] = original.document.nodes
  expect(original.document.edges.map(e => e.sourceHandle)).toEqual(['true', 'false'])
  expect(blockNodes(original, start.id)).toEqual([start.id, end.id])
  expect(deleteSelection(original, [end.id], []).document).toEqual(original.document)
  const copied = pasteNodes(original, original, [start.id], { x: 100, y: 100 })
  const [newStart, newEnd] = copied.content.document.nodes.slice(2)
  expect(newStart.config.endNodeId).toBe(newEnd.id)
  expect(newEnd.config.ownerNodeId).toBe(newStart.id)
  expect(newStart.id).not.toBe(start.id)
  const history = editHistory(createHistory(original), deleteSelection(original, [start.id], []))
  expect(history.present.document.nodes).toHaveLength(0)
  expect(undoHistory(history).present).toEqual(original)
})

it('renames local references only inside the loop and leaves typed literal placeholders untouched', () => {
  let content = addNode(createWorkflow(), definition('loop', { indexVariable: 'index', itemVariable: 'item', mode: 'count' }), { x: 0, y: 0 })
  const [loop, end] = content.document.nodes
  content = addNode(content, definition('set_variable', { value: { kind: 'variable', name: 'index', path: [] }, variableName: 'result' }), { x: 50, y: 0 })
  const body = content.document.nodes[2]
  content = deleteSelection(content, [], content.document.edges.map(e => e.id))
  content = connectNodes(content, loop.id, body.id, 'body').content
  content = connectNodes(content, body.id, end.id).content
  content = addNode(content, definition('set_variable', { value: { kind: 'literal', value: '{index}' }, variableName: 'outside' }), { x: 500, y: 0 })
  const outside = content.document.nodes[3]
  content = connectNodes(content, loop.id, outside.id, 'done').content
  const renamed = renameLoopVariable(content, loop.id, 'indexVariable', 'row')
  expect(renamed.document.nodes[2].config.value).toEqual({ kind: 'variable', name: 'row', path: [] })
  expect(renamed.document.nodes[3].config.value).toEqual({ kind: 'literal', value: '{index}' })
  expect(blockNodes(content, loop.id)).not.toContain(outside.id)
  expect(deleteSelection(content, [loop.id], []).document.nodes.map(n => n.id)).toEqual([outside.id])
  expect(renameVariable(content, 'index', 'newName').document.nodes[3].config.value).toEqual({ kind: 'literal', value: '{index}' })
})

it('normalizes old format signatures without marking a loaded flow dirty', () => {
  const content = createWorkflow()
  expect(signature({ ...content, document: { ...content.document, schemaVersion: 1 } })).toBe(signature(content))
})

it('presents three loop entries and hides paired ends from the action library', async () => {
  const add = vi.fn()
  render(<NodeCatalog items={[definition('loop'), definition('loop_end'), definition('condition_end')]} onAdd={add} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '添加遍历列表' }))
  expect(add).toHaveBeenCalledWith('loop:foreach')
  expect(screen.getByRole('button', { name: '添加重复指定次数' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '添加条件成立时循环' })).toBeInTheDocument()
  expect(screen.queryByText('loop_end')).not.toBeInTheDocument()
})

it('edits typed conditions without evaluating literal text and exposes page locator tools', async () => {
  const content = addNode(createWorkflow(), definition('condition', { match: 'all', rules: [{ kind: 'value', operator: 'eq', left: { kind: 'literal', value: '{literal}' }, right: { kind: 'literal', value: '' } }] }), { x: 0, y: 0 })
  const change = vi.fn()
  const view = render(<ControlFields node={content.document.nodes[0]} names={['item']} onChange={change} renderTools={() => <button>真实定位入口</button>} />)
  const user = userEvent.setup()
  await user.selectOptions(screen.getByLabelText('规则1类型'), 'page')
  const changed = patchNode(content, content.document.nodes[0].id, { config: change.mock.calls.at(-1)![0] })
  view.rerender(<ControlFields node={changed.document.nodes[0]} names={['item']} onChange={change} renderTools={() => <button>真实定位入口</button>} />)
  expect(screen.getByRole('button', { name: '真实定位入口' })).toBeInTheDocument()
  expect(screen.getByLabelText('规则1选择器')).toHaveValue('')
})

it('keeps ordinary object initial values separate from structured literal sources', async () => {
  const { referencedVariables } = await import('../editor-model')
  const value = { kind: 'literal', value: '{target}' }
  expect(referencedVariables(value)).toEqual(['target'])
  expect(referencedVariables(value, true)).toEqual([])
})
