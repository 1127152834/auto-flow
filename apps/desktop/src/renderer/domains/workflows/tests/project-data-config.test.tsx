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

async function checkFieldDeletionPreview(blocked: boolean) {
  const { apiRequest } = await import('../api')
  vi.mocked(apiRequest).mockClear()
  const field = { ref: { fieldId: 'old-field' }, key: 'old', name: '旧字段', type: 'string', required: false, validation: {}, fieldRevision: 1 }
  vi.mocked(apiRequest).mockImplementation(async path => ({ success: true, data: path.endsWith('/schema/preview') ? { impactRevision: 7, calculatedAt: '', expiresAt: '', affectedRecords: 1, backfillBytes: 2, blockers: blocked ? [{ code: 'SOURCE_FIELD_MAPPING', fieldId: 'old-field', clientId: null, message: '字段仍有来源列映射', affectedRecords: null }] : [], warnings: [], referenceAvailability: { automations: 'available', sync: 'available' } } : { items: path.endsWith('/fields') ? [field] : path.includes('/tables?') ? [{ tableId: 'table', datasetGeneration: 'generation', name: '来源', tableRevision: 2 }] : [], total: 1 } }) as never)
  const change = vi.fn()
  render(<ProjectDataConfig data={{ moduleType: 'project_data', operation: 'deleteField', bindingProjectId: 'project', tableGrant: { tableId: 'table', datasetGeneration: 'generation', operations: ['deleteField'], fieldIds: [], readPurposes: [] }, arguments: { tableId: 'table', datasetGeneration: 'generation', fieldId: 'old-field', impactRevision: "{field_deletion_preview['impactRevision']}" } } as unknown as NodeData} onChange={change} />)
  await waitFor(() => expect((screen.getByRole('button', { name: '预览删除影响' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '预览删除影响' }))
  const confirm = await screen.findByRole('button', { name: '确认删除目标' }) as HTMLButtonElement
  expect(confirm.disabled).toBe(blocked)
  if (blocked) {
    expect((await screen.findByRole('alert')).textContent).toContain('字段仍有来源列映射')
    expect(change).not.toHaveBeenCalled()
  } else {
    fireEvent.click(confirm)
    expect(change).toHaveBeenCalledWith('tableGrant', { tableId: 'table', datasetGeneration: 'generation', operations: ['deleteField'], fieldIds: ['old-field'], readPurposes: [] })
  }
  const calls = vi.mocked(apiRequest).mock.calls.filter(([path]) => path.endsWith('/schema/preview'))
  expect(calls).toHaveLength(1)
  expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ datasetGeneration: 'generation', expectedTableRevision: 2, removedFieldIds: ['old-field'], fields: [] })
  expect(vi.mocked(apiRequest).mock.calls.some(([path, options]) => options?.method === 'DELETE' || path.endsWith('/schema'))).toBe(false)
}

it('previews a field removal and grants that target only after confirmation', () => checkFieldDeletionPreview(false))
it('blocks field deletion confirmation while source mapping remains', () => checkFieldDeletionPreview(true))
