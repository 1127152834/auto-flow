import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { NodeData } from '../../editor-store'
import { ProjectDataConfig } from './ProjectDataConfig'

const request = vi.hoisted(() => vi.fn())
vi.mock('../../api', () => ({ apiRequest: request }))
vi.mock('../../api/config', () => ({ getBackendBaseUrl: () => 'http://local.test' }))
const scroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
afterEach(() => {
  cleanup()
  if (scroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', scroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})
beforeEach(() => { request.mockReset(); Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() }) })

const data = {
  moduleType: 'project_data', label: '项目数据', operation: 'updateRecord', bindingProjectId: 'project',
  tableGrant: { tableId: 'table', datasetGeneration: 'generation', operations: ['updateRecord'], fieldIds: [], readPurposes: ['condition', 'derivedWrite'] },
  arguments: { recordRef: "{record['ref']}", changes: {}, expectedContentRevision: "{record['contentRevision']}" }, variableName: 'saved',
} as NodeData
const table = { projectId: 'project', tableId: 'table', datasetGeneration: 'generation', name: '业务记录', tableRevision: 1 }
const field = { key: 'result', name: '结果', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1, ref: { projectId: 'project', tableId: 'table', datasetGeneration: 'generation', fieldId: 'field' } }

function successfulResponse(path: string) {
  if (path.startsWith('/v1/projects?pageSize=')) return { success: true, data: { items: [{ projectId: 'project', name: '当前项目' }], total: 1 } }
  if (path.includes('/tables?')) return { success: true, data: { items: [table, { ...table, tableId: 'other', datasetGeneration: 'other-generation', name: '另一张表' }], total: 2 } }
  if (path.endsWith('/fields')) return { success: true, data: { items: [field] } }
  if (path.endsWith('/statuses')) return { success: true, data: { items: [] } }
  throw new Error(`unexpected request: ${path}`)
}

test('freezes the canonical table grant generation and only explicitly selected fields', async () => {
  request.mockImplementation(async (path: string) => successfulResponse(path))
  const change = vi.fn()
  render(<ProjectDataConfig data={data} onChange={change} />)
  fireEvent.click(await screen.findByRole('checkbox', { name: /结果/ }))
  expect(change).toHaveBeenCalledWith('tableGrant', { tableId: 'table', datasetGeneration: 'generation', operations: ['updateRecord'], fieldIds: ['field'], readPurposes: ['condition', 'derivedWrite'] })
  fireEvent.keyDown(screen.getByLabelText('授权数据表'), { key: 'ArrowDown' })
  fireEvent.keyDown(await screen.findByRole('option', { name: '另一张表' }), { key: 'Enter' })
  expect(change).toHaveBeenCalledWith('tableGrant', { tableId: 'other', datasetGeneration: 'other-generation', operations: ['updateRecord'], fieldIds: [], readPurposes: ['condition', 'derivedWrite'] })
})

test('rejects fields from a changed dataset without rewriting the saved canonical grant', async () => {
  request.mockImplementation(async (path: string) => {
    if (path.startsWith('/v1/projects?pageSize=')) return { success: true, data: { items: [{ projectId: 'project', name: '当前项目' }], total: 1 } }
    if (path.includes('/tables?')) return { success: true, data: { items: [], total: 0 } }
    if (path.endsWith('/fields')) return { success: true, data: { items: [{ ...field, name: '新字段', ref: { ...field.ref, datasetGeneration: 'replacement' } }] } }
    throw new Error(`unexpected request: ${path}`)
  })
  const change = vi.fn()
  render(<ProjectDataConfig data={data} onChange={change} />)
  expect((await screen.findByRole('alert')).textContent).toContain('数据表版本已变化')
  expect(screen.queryByLabelText('新字段')).toBeNull()
  expect(change).not.toHaveBeenCalled()
})

test('surfaces a read failure and retries without rewriting the saved grant', async () => {
  request.mockResolvedValueOnce({ success: false, error: '数据目录不可用' })
  const change = vi.fn()
  render(<ProjectDataConfig data={data} onChange={change} />)
  expect((await screen.findByRole('alert')).textContent).toContain('项目列表读取失败')
  request.mockImplementation(async (path: string) => successfulResponse(path))
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findByText('业务记录')).toBeTruthy()
  expect(change).not.toHaveBeenCalled()
})
