import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import { ConfigPanel } from '../components/ConfigPanel'
import { mockRequest } from '../api/mock-server'
import { executeClientAction } from '../api/aiAssistantSkills'
import { getNodeConfigData, useWorkflowStore as store } from '../editor-store'
import { reviewSelectorHeals } from '../lib/selectorHealing'
import { staticNumberIssues } from '../lib/staticNumberPreflight'

Element.prototype.scrollIntoView = vi.fn()

const nestedDocument = () => ({
  id: 'nested-document',
  name: 'Nested document',
  browserEnvironmentVersion: 1,
  nodes: [
    {
      id: 'end',
      type: 'project_end',
      position: { x: 10, y: 20 },
      data: {
        moduleType: 'project_end',
        label: '项目结束',
        name: '外层节点备注',
        editorMetadata: { owner: 'fixture' },
        config: {
          retainEnvironment: true,
          name: '运行环境名称',
          inputIds: [],
          futureOption: { keep: true },
        },
      },
      customNodeMetadata: { keep: true },
    },
    {
      id: 'open',
      type: 'open_page',
      position: { x: 220, y: 20 },
      data: {
        moduleType: 'open_page',
        label: '打开网页',
        url: 'https://stale-outer.example/',
        openMode: 'current_tab',
        retryCount: 11,
        config: { url: 'https://before.example/', timeout: -1, futureWebOption: 'keep' },
      },
    },
  ],
  edges: [{ id: 'end-open', source: 'end', target: 'open' }],
  variables: [],
  editorMetadata: { viewport: { x: 3, y: 4, zoom: 1 } },
})

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

it('reads and edits nested runtime config without overwriting outer editor metadata', () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  render(<ConfigPanel selectedNodeId="end" />)

  expect((screen.getByRole('checkbox', { name: '保留当前环境并关联记录' }) as HTMLInputElement).checked).toBe(true)
  expect((screen.getByLabelText('节点备注') as HTMLInputElement).value).toBe('外层节点备注')
  expect((screen.getByLabelText('新环境名称') as HTMLInputElement).value).toBe('运行环境名称')

  fireEvent.change(screen.getByLabelText('新环境名称'), { target: { value: '修改后的运行环境' } })
  const data = store.getState().nodes[0].data as Record<string, unknown>
  expect(data.name).toBe('外层节点备注')
  expect(data.editorMetadata).toEqual({ owner: 'fixture' })
  expect(data.config).toEqual({
    retainEnvironment: true,
    name: '修改后的运行环境',
    inputIds: [],
    futureOption: { keep: true },
  })
})

it('shows, preserves and clears nested static End targets without converting them to a string', () => {
  const document = nestedDocument()
  const targets = [{ recordRef: { projectId: 'project-test', tableId: 'accounts', recordId: 'row-1' }, expectedLinkRevision: 2 }]
  Object.assign(document.nodes[0].data, { recordTargets: [{ recordRef: { recordId: 'stale-outer' } }] })
  Object.assign(document.nodes[0].data.config, { recordTargets: targets })
  expect(store.getState().importWorkflow(document)).toBe(true)
  render(<ConfigPanel selectedNodeId="end" />)

  expect(JSON.parse((screen.getByRole('textbox', { name: '静态记录目标' }) as HTMLTextAreaElement).value)).toEqual(targets)
  fireEvent.click(screen.getByRole('checkbox', { name: '允许替换所选记录已有的环境关联' }))
  let data = store.getState().nodes[0].data as Record<string, unknown>
  expect((data.config as Record<string, unknown>).recordTargets).toEqual(targets)
  expect(data.recordTargets).toEqual([{ recordRef: { recordId: 'stale-outer' } }])

  fireEvent.click(screen.getByRole('button', { name: '清空记录目标' }))
  data = store.getState().nodes[0].data as Record<string, unknown>
  expect((data.config as Record<string, unknown>).recordTargets).toEqual([])
  expect(data.recordTargets).toEqual([{ recordRef: { recordId: 'stale-outer' } }])
})

it.each(['open', 'merge'] as const)('preserves nested config through the real %s and export entrypoints', mode => {
  const document = nestedDocument()
  const accepted = mode === 'open'
    ? store.getState().importWorkflow(document)
    : store.getState().mergeWorkflow(JSON.stringify(document), { x: 500, y: 300 })
  expect(accepted).toBe(true)
  const exported = JSON.parse(store.getState().exportWorkflow())
  const end = exported.nodes.find((node: { data: { moduleType: string } }) => node.data.moduleType === 'project_end')
  expect(end.data).toMatchObject({
    name: '外层节点备注',
    editorMetadata: { owner: 'fixture' },
    config: { retainEnvironment: true, name: '运行环境名称', futureOption: { keep: true } },
  })
  expect(end.customNodeMetadata).toEqual({ keep: true })
})

it('saves and reloads the edited effective config through the document transport boundary', async () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  const view = render(<ConfigPanel selectedNodeId="open" />)
  const urlGroup = screen.getByText('网址', { exact: true }).parentElement!
  fireEvent.change(within(urlGroup).getByRole('textbox'), { target: { value: 'https://after.example/' } })

  const content = JSON.parse(store.getState().exportWorkflow())
  const saved = await mockRequest('http://autoflow-studio.mock/api/local-workflows/save-to-folder', {
    method: 'POST', body: JSON.stringify({ filename: 'nested-config', content }),
  })
  expect(saved.status).toBe(200)
  const loaded = await (await mockRequest('http://autoflow-studio.mock/api/local-workflows/load/nested-config.json')).json()
  view.unmount()
  act(() => {
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(loaded.content)).toBe(true)
  })

  const data = store.getState().nodes.find(node => node.id === 'open')!.data as Record<string, unknown>
  expect(data.config).toEqual({
    url: 'https://after.example/', timeout: -1, futureWebOption: 'keep',
  })
  expect(data.url).toBe('https://stale-outer.example/')
  render(<ConfigPanel selectedNodeId="open" />)
  const reloadedUrlGroup = screen.getByText('网址', { exact: true }).parentElement!
  expect((within(reloadedUrlGroup).getByRole('textbox') as HTMLInputElement).value).toBe('https://after.example/')
})

it('uses nested runtime config for shared preflight and preserves flat behavior', () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  const effective = getNodeConfigData(store.getState().nodes[1].data)
  expect(effective).toMatchObject({ moduleType: 'open_page', label: '打开网页', url: 'https://before.example/' })
  expect(effective.openMode).toBeUndefined()
  expect(effective.retryCount).toBeUndefined()
  expect(staticNumberIssues(store.getState().nodes)).toContainEqual({
    nodeId: 'open', path: 'data.timeout', message: '超时时间不能小于0',
  })
  expect(staticNumberIssues(store.getState().nodes).some(issue => issue.path === 'data.retryCount')).toBe(false)

  act(() => {
    store.getState().clearWorkflow()
    store.getState().addNode('open_page', { x: 0, y: 0 })
  })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)
  const urlGroup = screen.getByText('网址', { exact: true }).parentElement!
  fireEvent.change(within(urlGroup).getByRole('textbox'), { target: { value: 'https://flat.example/' } })
  expect(store.getState().nodes[0].data).toMatchObject({ url: 'https://flat.example/' })
  expect(store.getState().nodes[0].data.config).toBeUndefined()
})

it('batches nested config changes into one undo step and skips identical updates', () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  store.getState().markAsSaved()
  store.getState().updateNodesConfig([
    { nodeId: 'open', data: { url: 'https://first.example/' } },
    { nodeId: 'open', data: { waitUntil: 'networkidle' } },
    { nodeId: 'open', data: { url: 'https://last.example/' } },
  ])
  expect(store.getState().nodes[1].data.config).toMatchObject({
    url: 'https://last.example/', waitUntil: 'networkidle', futureWebOption: 'keep',
  })
  store.getState().undo()
  expect(store.getState().nodes[1].data.config).toEqual(nestedDocument().nodes[1].data.config)
  store.getState().redo()
  store.getState().markAsSaved()
  const stableHistory = store.getState().history
  const current = store.getState().nodes[1].data.config as Record<string, unknown>
  store.getState().updateNodeConfig('open', { url: String(current.url) })
  expect(store.getState().history).toBe(stableHistory)
  expect(store.getState().hasUnsavedChanges).toBe(false)
})

it('routes assistant configuration edits through the same nested write boundary', async () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  const response = await executeClientAction('update_node_config', {
    node_id: 'open', config: { url: 'https://assistant.example/', waitUntil: 'networkidle' },
  })
  expect(response.success).toBe(true)
  const data = store.getState().nodes[1].data as Record<string, unknown>
  expect(data.url).toBe('https://stale-outer.example/')
  expect(data.config).toMatchObject({
    url: 'https://assistant.example/', waitUntil: 'networkidle', futureWebOption: 'keep',
  })
})

it('keeps an assistant label compatibility rename outside nested End runtime config', async () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  const response = await executeClientAction('update_node_config', {
    node_id: 'end', config: { label: 'AI 单项备注', retainEnvironment: false },
  })
  expect(response.success).toBe(true)
  const data = store.getState().nodes[0].data as Record<string, unknown>
  expect(data.name).toBe('AI 单项备注')
  expect(data.config).toMatchObject({
    name: '运行环境名称', retainEnvironment: false, futureOption: { keep: true },
  })
})

it('keeps assistant batch labels as outer remarks while updating nested runtime fields', async () => {
  expect(store.getState().importWorkflow(nestedDocument())).toBe(true)
  const response = await executeClientAction('bulk_update_nodes', {
    patches: [
      { node_id: 'end', config: { label: 'AI 批量 End 备注', retainEnvironment: false } },
      { node_id: 'open', config: { label: 'AI 批量网页备注', url: 'https://batch.example/' } },
    ],
  })
  expect(response.success).toBe(true)
  const [end, open] = store.getState().nodes.map(node => node.data as Record<string, unknown>)
  expect(end.name).toBe('AI 批量 End 备注')
  expect(end.config).toMatchObject({ name: '运行环境名称', retainEnvironment: false })
  expect(open.name).toBe('AI 批量网页备注')
  expect(open.config).toMatchObject({ url: 'https://batch.example/', futureWebOption: 'keep' })
})

it.each([
  {
    node: {
      id: 'group', type: 'groupNode', position: { x: 0, y: 0 },
      data: { moduleType: 'group', label: '外层分组标签', config: { isSubflow: true, subflowName: '内层分组名', futureGroupOption: 'keep' } },
    },
    previousLabel: '外层分组标签', previousName: '内层分组名', next: '修改后的分组名', futureKey: 'futureGroupOption',
  },
  {
    node: {
      id: 'header', type: 'subflowHeaderNode', position: { x: 0, y: 0 },
      data: { moduleType: 'subflow_header', label: '外层函数头标签', config: { subflowName: '内层函数头名', futureHeaderOption: 'keep' } },
    },
    previousLabel: '外层函数头标签', previousName: '内层函数头名', next: '修改后的函数头名', futureKey: 'futureHeaderOption',
  },
])('writes $node.type label metadata outside nested subflow config', ({ node, previousLabel, previousName, next, futureKey }) => {
  expect(store.getState().importWorkflow({ id: 'nested-structure', name: 'Nested structure', nodes: [node], edges: [], variables: [] })).toBe(true)
  render(<ConfigPanel selectedNodeId={node.id} />)
  const input = screen.getByPlaceholderText('子流程名称')
  fireEvent.change(input, { target: { value: next } })

  const data = store.getState().nodes[0].data as Record<string, unknown>
  expect(data.label).toBe(next)
  expect(data.config).toMatchObject({ subflowName: next, [futureKey]: 'keep' })
  expect((data.config as Record<string, unknown>).label).toBeUndefined()
  store.getState().undo()
  expect(store.getState().nodes[0].data.label).toBe(previousLabel)
  expect(store.getState().nodes[0].data.config).toMatchObject({ subflowName: previousName, [futureKey]: 'keep' })
})

it('writes selector healing into nested config without reviving a stale outer selector', async () => {
  const document = nestedDocument()
  Object.assign(document.nodes[1].data, {
    selector: '#stale-outer',
    config: { ...document.nodes[1].data.config, selector: '#old' },
  })
  expect(store.getState().importWorkflow(document)).toBe(true)

  await reviewSelectorHeals({
    documentId: 'nested-document',
    heals: [{ nodeId: 'open', configKey: 'selector', oldSelector: '#old', newSelector: '#healed' }],
  }, async () => true)

  const data = store.getState().nodes[1].data as Record<string, unknown>
  expect(data.selector).toBe('#stale-outer')
  expect(data.config).toMatchObject({ selector: '#healed', futureWebOption: 'keep' })
})
