import { describe, expect, it } from 'vitest'
import { addNode, connectNodes, createWorkflow, deleteSelection, pasteNodes, renameVariable, referencedVariables, signature } from '../editor-model'
import { createHistory, editHistory, undoHistory, redoHistory } from '../history'
import type { NodeDefinition } from '../types'

const definition: NodeDefinition = { type: 'open_page', title: '打开网页', description: '', category: '网页', defaultConfig: { url: '', timeoutSeconds: 60 }, configSchema: {}, inputPorts: ['in'], outputPorts: ['out'], runnable: false }
function pair() {
  let content = addNode(createWorkflow(), definition, { x: 10, y: 20 })
  content = addNode(content, definition, { x: 210, y: 20 })
  return connectNodes(content, content.document.nodes[0].id, content.document.nodes[1].id).content
}

describe('workflow document edits', () => {
  it('starts empty and rejects self, duplicate, branch and cyclic connections', () => {
    const empty = createWorkflow()
    expect(empty.document.nodes).toEqual([])
    const content = pair()
    const [a, b] = content.document.nodes
    expect(connectNodes(content, a.id, a.id).error).toBeTruthy()
    expect(connectNodes(content, a.id, b.id).error).toBeTruthy()
    expect(connectNodes(content, b.id, a.id).error).toBeTruthy()
    const third = addNode(content, definition, { x: 500, y: 20 })
    expect(connectNodes(third, a.id, third.document.nodes[2].id).error).toBeTruthy()
  })

  it('deletes incident edges and restores the whole graph with undo', () => {
    const content = pair()
    const history = editHistory(createHistory(content), deleteSelection(content, [content.document.nodes[0].id], []))
    expect(history.present.document.edges).toEqual([])
    expect(Object.keys(history.present.layout.nodes)).toHaveLength(1)
    const restored = undoHistory(history)
    expect(restored.present.document).toEqual(content.document)
    expect(redoHistory(restored).present.document.nodes).toHaveLength(1)
  })

  it('pastes new identities and only edges inside the copied selection', () => {
    const content = pair()
    const pasted = pasteNodes(content, content, content.document.nodes.map(n => n.id), { x: 400, y: 300 })
    expect(new Set(pasted.content.document.nodes.map(n => n.id)).size).toBe(4)
    expect(pasted.content.document.edges).toHaveLength(2)
    expect(pasted.ids).toHaveLength(2)
    expect(pasted.content.layout.nodes[pasted.ids[0]]).toEqual({ x: 400, y: 300 })
  })

  it('renames exact variable references atomically without changing literals or credentials', () => {
    const content = pair()
    content.document.nodes[1].type = 'get_element_info'
    content.document.nodes[1].config = { variableName: 'name', selector: 'body' }
    content.document.variables = [{ name: 'name', type: 'string', value: 'Ada' }]
    content.document.nodes[0].config.url = 'https://site/{name}/${name}/{names}/{{cred:name}}'
    const renamed = renameVariable(content, 'name', 'person')
    expect(renamed.document.nodes[0].config.url).toBe('https://site/{person}/${person}/{names}/{{cred:name}}')
    expect(renamed.document.nodes[1].config.variableName).toBe('person')
    expect(renamed.document.variables[0].name).toBe('person')
    expect(referencedVariables(renamed.document.nodes[0].config)).toEqual(['person', 'person', 'names'])
    const restored = undoHistory(editHistory(createHistory(content), renamed))
    expect(restored.present.document).toEqual(content.document)
  })

  it('does not treat viewport-only changes as dirty or undoable content', () => {
    const content = pair()
    const moved = { ...content, layout: { ...content.layout, viewport: { x: 30, y: 40, zoom: 2 } } }
    expect(signature(moved)).toBe(signature(content))
    expect(editHistory(createHistory(content), moved).past).toHaveLength(0)
  })

  it('groups a drag or field edit into one undo step and preserves the current viewport', () => {
    const content = pair()
    const id = content.document.nodes[0].id
    const intermediate = { ...content, layout: { ...content.layout, nodes: { ...content.layout.nodes, [id]: { x: 40, y: 20 } } } }
    const end = { ...intermediate, layout: { ...intermediate.layout, nodes: { ...intermediate.layout.nodes, [id]: { x: 80, y: 20 } }, viewport: { x: 5, y: 6, zoom: 1.5 } } }
    let history = editHistory(createHistory(content), intermediate)
    history = editHistory(history, end, true)
    expect(history.past).toHaveLength(1)
    expect(undoHistory(history).present.layout.nodes[id]).toEqual({ x: 10, y: 20 })
    expect(undoHistory(history).present.layout.viewport).toEqual(end.layout.viewport)
  })
})
