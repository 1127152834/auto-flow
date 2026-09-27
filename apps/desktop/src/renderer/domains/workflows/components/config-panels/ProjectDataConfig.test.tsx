import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { NodeData } from '../../editor-store'
import { ProjectDataConfig } from './ProjectDataConfig'

const request = vi.hoisted(() => vi.fn())
vi.mock('../../api', () => ({ apiRequest: request }))
vi.mock('../../api/config', () => ({ getBackendBaseUrl: () => 'http://local.test', getStudioOpenContext: () => ({ projectId: 'project' }) }))
const scroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
afterEach(() => {
  cleanup()
  if (scroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', scroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})
beforeEach(() => { request.mockReset(); Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() }) })
const data = { moduleType: 'project_data', label: '项目数据', action: 'update', binding: { tableId: 'table', datasetGeneration: 'generation', fieldIds: [] } } as NodeData

test('freezes selected table generation and only explicitly selected fields', async () => {
  request.mockImplementation(async (path: string) => ({ success: true, data: path.endsWith('/fields')
    ? { items: [{ name: '结果', ref: { projectId: 'project', tableId: 'table', datasetGeneration: 'generation', fieldId: 'field' } }] }
    : { items: [{ name: '业务记录', tableId: 'table', datasetGeneration: 'generation' }, { name: '另一张表', tableId: 'other', datasetGeneration: 'other-generation' }], total: 2 } }))
  const change = vi.fn()
  render(<ProjectDataConfig data={data} onChange={change} />)
  expect(await screen.findByText('业务记录')).toBeTruthy()
  fireEvent.click(await screen.findByLabelText('结果'))
  expect(change).toHaveBeenCalledWith('binding', { tableId: 'table', datasetGeneration: 'generation', fieldIds: ['field'] })
  fireEvent.keyDown(screen.getByLabelText('授权数据表'), { key: 'ArrowDown' })
  fireEvent.keyDown(await screen.findByRole('option', { name: '另一张表' }), { key: 'Enter' })
  expect(change).toHaveBeenLastCalledWith('binding', { tableId: 'other', datasetGeneration: 'other-generation', fieldIds: [] })
  const argumentsText = '{"expectedContentRevision": {record["result"]["contentRevision"]}}'
  fireEvent.change(screen.getByLabelText('操作参数（JSON）'), { target: { value: argumentsText } })
  expect(change).toHaveBeenLastCalledWith('arguments', argumentsText)
})

test('rejects fields from a changed dataset without rewriting saved binding', async () => {
  request.mockImplementation(async (path: string) => ({ success: true, data: path.endsWith('/fields')
    ? { items: [{ name: '新字段', ref: { projectId: 'project', tableId: 'table', datasetGeneration: 'replacement', fieldId: 'field' } }] }
    : { items: [], total: 0 } }))
  const change = vi.fn()
  render(<ProjectDataConfig data={data} onChange={change} />)
  expect((await screen.findByRole('alert')).textContent).toContain('数据表版本已变化')
  expect(screen.queryByLabelText('新字段')).toBeNull()
  expect(change).not.toHaveBeenCalled()
})

test('surfaces read failure and allows an explicit retry', async () => {
  request.mockResolvedValue({ success: false, error: '数据目录不可用' })
  render(<ProjectDataConfig data={data} onChange={vi.fn()} />)
  expect((await screen.findByRole('alert')).textContent).toContain('数据目录不可用')
  request.mockResolvedValue({ success: true, data: { items: [], total: 0 } })
  fireEvent.click(screen.getByRole('button', { name: '重试读取' }))
  expect(await screen.findByText('原数据表待核验')).toBeTruthy()
})
