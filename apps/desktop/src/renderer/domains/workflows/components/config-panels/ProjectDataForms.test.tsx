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

const uuid = (n: number) => `123e4567-e89b-12d3-a456-42661417400${n}`
const ref = (fieldId: string) => ({ projectId: 'project', tableId: 'table', datasetGeneration: 'generation', fieldId })
const base = { required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
const fieldA = { ...base, key: 'result', name: '结果', type: 'string', ref: ref(uuid(1)) }
const fieldB = { ...base, key: 'count', name: '次数', type: 'number', ref: ref(uuid(2)) }
const table = { projectId: 'project', tableId: 'table', datasetGeneration: 'generation', name: '业务记录', tableRevision: 1 }
function respond(path: string) {
  if (path.startsWith('/v1/projects?pageSize=')) return { success: true, data: { items: [{ projectId: 'project', name: '当前项目' }], total: 1 } }
  if (path.includes('/tables?')) return { success: true, data: { items: [table], total: 1 } }
  if (path.endsWith('/fields')) return { success: true, data: { items: [fieldA, fieldB] } }
  if (path.endsWith('/statuses')) return { success: true, data: { items: [{ statusId: uuid(3), name: '已完成' }] } }
  throw new Error(`unexpected request: ${path}`)
}
beforeEach(() => {
  request.mockReset(); request.mockImplementation(async (path: string) => respond(path))
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
})

const nodeData = (operation: string, args: Record<string, unknown>) => ({
  moduleType: 'project_data', label: '项目数据', operation, bindingProjectId: 'project', variableName: 'saved', arguments: args,
  tableGrant: { tableId: 'table', datasetGeneration: 'generation', operations: [operation], fieldIds: [], readPurposes: ['condition', 'derivedWrite'] },
}) as unknown as NodeData
const lastCall = (change: ReturnType<typeof vi.fn>, key: string) => change.mock.calls.filter(([k]) => k === key).at(-1)?.[1]
async function pick(label: string, name: string) {
  fireEvent.keyDown(screen.getByLabelText(label), { key: 'ArrowDown' })
  fireEvent.keyDown(await screen.findByRole('option', { name }), { key: 'Enter' })
}

test('update form shows saved changes by field name and writes them back without losing other settings', async () => {
  const change = vi.fn()
  const args = { recordRef: "{record['ref']}", changes: { [uuid(1)]: '成功' }, expectedContentRevision: 7 }
  render(<ProjectDataConfig data={nodeData('updateRecord', args)} onChange={change} />)
  expect(((await screen.findByLabelText('写入值 1')) as HTMLInputElement).value).toBe('成功')
  expect(screen.queryByRole('checkbox', { name: /结果/ })).toBeNull()
  fireEvent.change(screen.getByLabelText('写入值 1'), { target: { value: '失败' } })
  expect(lastCall(change, 'arguments')).toEqual({ ...args, changes: { [uuid(1)]: '失败' } })
  expect(lastCall(change, 'tableGrant')).toMatchObject({ operations: ['updateRecord'], fieldIds: [uuid(1)] })
  fireEvent.click(screen.getByRole('button', { name: '添加字段' }))
  await pick('写入字段 2', '次数')
  fireEvent.change(screen.getByLabelText('写入值 2'), { target: { value: '3' } })
  expect(lastCall(change, 'arguments').changes).toEqual({ [uuid(1)]: '失败', [uuid(2)]: 3 })
  expect(lastCall(change, 'tableGrant').fieldIds).toEqual([uuid(1), uuid(2)])
  fireEvent.click(screen.getByRole('button', { name: '删除写入字段 1' }))
  expect(lastCall(change, 'arguments').changes).toEqual({ [uuid(2)]: 3 })
})

test('create form writes values keyed by field and keeps references as text', async () => {
  const change = vi.fn()
  render(<ProjectDataConfig data={nodeData('createRecord', { tableId: 'table', datasetGeneration: 'generation', values: {} })} onChange={change} />)
  fireEvent.click(await screen.findByRole('button', { name: '添加字段' }))
  await pick('写入字段 1', '结果')
  fireEvent.change(screen.getByLabelText('写入值 1'), { target: { value: '{browser_result}' } })
  expect(lastCall(change, 'arguments')).toEqual({ tableId: 'table', datasetGeneration: 'generation', values: { [uuid(1)]: '{browser_result}' } })
})

test('status form saves the chosen status by name', async () => {
  const change = vi.fn()
  const args = { recordRef: "{record['ref']}", statusId: null, expectedStatusRevision: "{record['statusRevision']}" }
  render(<ProjectDataConfig data={nodeData('setRecordStatus', args)} onChange={change} />)
  await screen.findByLabelText('设置为')
  await pick('设置为', '已完成')
  expect(lastCall(change, 'arguments')).toEqual({ ...args, statusId: uuid(3) })
})

test('query form builds condition rows and round-trips a saved filter', async () => {
  const change = vi.fn()
  const filter = { type: 'all', items: [{ type: 'compare', fieldId: uuid(1), operator: 'eq', value: '待处理' }] }
  const args = { tableId: 'table', datasetGeneration: 'generation', fieldIds: [uuid(2)], readPurpose: 'condition', filter, orderBy: [], cursor: null, limit: 100 }
  render(<ProjectDataConfig data={nodeData('queryRecords', args)} onChange={change} />)
  expect(((await screen.findByLabelText('比较值 1')) as HTMLInputElement).value).toBe('待处理')
  fireEvent.change(screen.getByLabelText('比较值 1'), { target: { value: '已完成' } })
  expect(lastCall(change, 'arguments')).toEqual({ ...args, filter: { type: 'all', items: [{ type: 'compare', fieldId: uuid(1), operator: 'eq', value: '已完成' }] } })
  expect(lastCall(change, 'tableGrant').fieldIds).toEqual([uuid(2), uuid(1)])
  fireEvent.click(screen.getByRole('button', { name: '添加条件' }))
  await pick('条件字段 2', '次数')
  await pick('比较方式 2', '大于')
  fireEvent.change(screen.getByLabelText('比较值 2'), { target: { value: '5' } })
  expect(lastCall(change, 'arguments').filter.items[1]).toEqual({ type: 'compare', fieldId: uuid(2), operator: 'gt', value: 5 })
  fireEvent.click(screen.getByRole('button', { name: '删除条件 2' }))
  fireEvent.click(screen.getByRole('button', { name: '删除条件 1' }))
  expect(lastCall(change, 'arguments').filter).toBeNull()
})

test('query form leaves a complex saved filter alone and still shows it under advanced', async () => {
  const filter = { type: 'any', items: [{ type: 'status', operator: 'isNull' }] }
  const change = vi.fn()
  render(<ProjectDataConfig data={nodeData('queryRecords', { filter })} onChange={change} />)
  expect(await screen.findByText(/不能逐行编辑/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '高级：直接编辑参数' }))
  expect(JSON.parse((screen.getByLabelText('操作参数（JSON，值可引用变量）') as HTMLTextAreaElement).value)).toEqual({ filter })
  expect(change).not.toHaveBeenCalled()
})

test('an old generic node keeps its operation and raw arguments', async () => {
  render(<ProjectDataConfig data={nodeData('deleteRecord', { recordRef: "{record['ref']}" })} onChange={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '高级：直接编辑参数' }))
  expect(JSON.parse((screen.getByLabelText('操作参数（JSON，值可引用变量）') as HTMLTextAreaElement).value)).toEqual({ recordRef: "{record['ref']}" })
})
