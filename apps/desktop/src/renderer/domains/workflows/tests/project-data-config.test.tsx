import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ProjectDataConfig } from '../components/config-panels/ProjectDataConfig'
import type { NodeData } from '../editor-store'
afterEach(cleanup)
vi.mock('../api', () => ({ apiRequest: vi.fn(async () => ({ success: true, data: { items: [] } })) }))
it('keeps task authority out of user arguments and supports a result variable', async () => {
  const change = vi.fn()
  render(<ProjectDataConfig data={{ label: '项目数据', moduleType: 'project_data', operation: 'createRecord', arguments: {}, variableName: 'saved' } as NodeData} onChange={change} />)
  const editor = screen.getByLabelText('操作参数（JSON，值可引用变量）')
  fireEvent.change(editor, { target: { value: '{"projectId":"forged"}' } }); fireEvent.blur(editor)
  expect((await screen.findByRole('alert')).textContent).toContain('不能在参数中覆盖')
  expect(change).toHaveBeenCalledWith('argumentsValid', false)
  expect(change.mock.calls.some(([key]) => key === 'arguments')).toBe(false)
  fireEvent.change(editor, { target: { value: '{"values":{"field":"{browser_result}"}}' } }); fireEvent.blur(editor)
  await waitFor(() => expect(change).toHaveBeenCalledWith('arguments', { values: { field: '{browser_result}' } }))
})

it('does not retain valid End arguments when the current JSON is invalid', async () => {
  const { ProjectLifecycleConfig } = await import('../components/config-panels/ProjectLifecycleConfig')
  const change = vi.fn()
  render(<ProjectLifecycleConfig data={{ moduleType: 'project_end', retainEnvironment: { enabled: true, mode: 'saveAs', recordTargets: [] } } as unknown as NodeData} onChange={change} />)
  const input = screen.getByLabelText('关联记录（JSON 数组，支持变量）')
  fireEvent.change(input, { target: { value: '{}' } }); fireEvent.blur(input)
  expect(change).toHaveBeenCalledWith('retentionValid', false)
})

it('binds field preview to the existing modifyField permission', async () => {
  Element.prototype.scrollIntoView = vi.fn()
  const { apiRequest } = await import('../api')
  vi.mocked(apiRequest).mockImplementation(async (path) => ({ success: true, data: { items: path.includes('/tables?') ? [{ tableId: 'table', datasetGeneration: 'generation', name: '来源', tableRevision: 1 }] : [], total: 1 } }) as never)
  const change = vi.fn()
  render(<ProjectDataConfig data={{ moduleType: 'project_data', operation: 'previewFieldChange', bindingProjectId: 'project', arguments: {}, variableName: 'preview' } as unknown as NodeData} onChange={change} />)
  await waitFor(() => expect(apiRequest).toHaveBeenCalledWith(expect.stringContaining('/tables?'), expect.anything()))
  fireEvent.keyDown(screen.getByLabelText('授权数据表'), { key: 'ArrowDown' })
  fireEvent.keyDown(await screen.findByRole('option', { name: '来源' }), { key: 'Enter' })
  expect(change).toHaveBeenCalledWith('tableGrant', expect.objectContaining({ operations: ['modifyField'] }))
})

it('selects explicit schema fields and keeps the query free of write authority', async () => {
  const { apiRequest } = await import('../api')
  vi.mocked(apiRequest).mockImplementation(async path => ({ success: true, data: { items: path.endsWith('/fields') ? [{ ref: { fieldId: 'field' }, name: '当前字段' }] : [], total: 0 } }) as never)
  const change = vi.fn()
  render(<ProjectDataConfig data={{ moduleType: 'project_data', operation: 'queryTableSchema', bindingProjectId: 'project', tableGrant: { tableId: 'table', datasetGeneration: 'generation', operations: ['queryTableSchema'], fieldIds: [], readPurposes: [] }, arguments: { tableId: 'table', datasetGeneration: 'generation', fieldIds: [] }, variableName: 'schema' } as unknown as NodeData} onChange={change} />)
  fireEvent.click(await screen.findByRole('checkbox', { name: /当前字段/ }))
  expect(change).toHaveBeenCalledWith('arguments', { tableId: 'table', datasetGeneration: 'generation', fieldIds: ['field'] })
  expect(change).toHaveBeenCalledWith('tableGrant', { tableId: 'table', datasetGeneration: 'generation', operations: ['queryTableSchema'], fieldIds: ['field'], readPurposes: [] })
  expect((screen.getByLabelText('结果变量') as HTMLInputElement).value).toBe('schema')
})
