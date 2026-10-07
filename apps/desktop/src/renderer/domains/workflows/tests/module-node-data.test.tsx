import { act, cleanup, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@xyflow/react', async (importOriginal) => {
  const original = await importOriginal<typeof import('@xyflow/react')>()
  return {
    ...original,
    Handle: () => null,
    useReactFlow: () => ({ fitView: vi.fn(), getNodes: vi.fn(() => []), setCenter: vi.fn() }),
  }
})
vi.mock('../lib/nodeIssues', () => ({ useNodeIssues: () => [] }))

import { findInternalIds } from '../../../shared/testing/internal-id-scan'
import { ModuleNode } from '../components/ModuleNode'
import { useWorkflowStore } from '../editor-store'
import { useDataSelectionStore } from '../hooks/stores/dataSelectionStore'
import { useSignatureStore } from '../hooks/stores/signatureStore'

const signature = [{ key: 'account', name: '账号', fields: [{ key: 'email', name: '邮箱', type: 'string', required: true, sensitive: false, rest: {} }], rest: {} }]
const renderNode = (data: Record<string, unknown>, id = 'n1') => render(
  <ModuleNode {...({ id, data: { label: '输入文本', moduleType: 'input_text', ...data }, selected: false } as unknown as ComponentProps<typeof ModuleNode>)} />,
)

beforeEach(() => {
  useSignatureStore.setState({ inputs: signature as never })
  useDataSelectionStore.getState().clear()
})
afterEach(() => cleanup())

describe('画布节点第二行数据标签', () => {
  it('引用显示成业务名，不出现原始引用串或内部标识', () => {
    renderNode({ selector: '#email', text: '{input.account.email}' })
    expect(screen.getByText('#email')).toBeTruthy()
    expect(screen.getByTestId('node-data-tag').textContent).toBe('账号·邮箱')
    expect(screen.getByTestId('module-node').textContent).not.toContain('{input')
    expect(findInternalIds(document.body)).toEqual([])
  })

  it('摘要里的引用直接显示为标签', () => {
    renderNode({ text: '{input.account.email}' })
    expect(screen.getAllByTestId('node-data-tag').map(tag => tag.textContent)).toEqual(['账号·邮箱'])
  })

  it('失效引用用警示样式显示“已失效的引用”', () => {
    renderNode({ text: '{input.account.gone}' })
    const tag = screen.getByTestId('node-data-tag-invalid')
    expect(tag.textContent).toBe('已失效的引用')
    expect(tag.className).toContain('bg-warning-soft')
    expect(screen.getByTestId('module-node').textContent).not.toContain('gone')
  })

  it('无引用时保持原摘要，也没有数据标签和读写角标', () => {
    renderNode({ moduleType: 'click_element', label: '点击元素', selector: '#submit' })
    expect(screen.getByText('#submit').className).toContain('text-[13px]')
    expect(screen.queryByTestId('node-data-tag')).toBeNull()
    expect(screen.queryByTestId('node-read-badge')).toBeNull()
    expect(screen.queryByTestId('node-write-badge')).toBeNull()
  })
})

describe('读/写角标', () => {
  it('含引用的节点显示读取角标', () => {
    renderNode({ text: '{input.account.email}' })
    const badge = screen.getByLabelText('读取数据')
    expect(badge.getAttribute('title')).toBe('读取数据')
    expect(screen.queryByTestId('node-write-badge')).toBeNull()
  })

  it('项目数据查询是读，新增/更新/设置状态是写', () => {
    renderNode({ moduleType: 'project_data', label: '项目数据', operation: 'queryRecords' })
    expect(screen.getByTestId('node-read-badge')).toBeTruthy()
    expect(screen.queryByTestId('node-write-badge')).toBeNull()
    cleanup()
    for (const operation of ['createRecord', 'updateRecord', 'setRecordStatus']) {
      renderNode({ moduleType: 'project_data', label: '项目数据', operation })
      const badge = screen.getByLabelText('写入项目数据')
      expect(badge.getAttribute('title')).toBe('写入项目数据')
      expect(screen.queryByTestId('node-read-badge')).toBeNull()
      cleanup()
    }
  })
})

describe('数据高亮', () => {
  it('选中数据行时引用它的节点高亮，其他节点不亮；取消后恢复', () => {
    renderNode({ text: '{input.account.email}' })
    renderNode({ text: '无关' }, 'n2')
    const [uses, other] = screen.getAllByTestId('module-node')
    expect(uses.getAttribute('data-data-highlighted')).toBeNull()
    act(() => useDataSelectionStore.getState().toggle('{input.account.email}'))
    expect(uses.getAttribute('data-data-highlighted')).toBe('true')
    expect(uses.className).toContain('!border-info')
    expect(other.getAttribute('data-data-highlighted')).toBeNull()
    act(() => useDataSelectionStore.getState().toggle('{input.account.email}'))
    expect(uses.getAttribute('data-data-highlighted')).toBeNull()
  })

  it('清除选择（Esc）后高亮消失', () => {
    renderNode({ text: '{input.account.email}' })
    act(() => useDataSelectionStore.getState().toggle('{input.account.email}'))
    act(() => useDataSelectionStore.getState().clear())
    expect(screen.getByTestId('module-node').getAttribute('data-data-highlighted')).toBeNull()
  })
})

describe('节点输出引用', () => {
  it('引用其他节点输出时显示 节点·输出名', () => {
    useWorkflowStore.setState({ nodes: [{ id: 'n7', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'ai_chat', label: '问答' } }] as never })
    renderNode({ text: '{node.n7.variableName}' })
    expect(screen.getByTestId('node-data-tag').textContent).toBe('问答·结果')
    expect(findInternalIds(document.body)).toEqual([])
    useWorkflowStore.setState({ nodes: [] })
  })
})
