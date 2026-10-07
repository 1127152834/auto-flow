import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ProjectDataConfig } from '../components/config-panels/ProjectDataConfig'
import type { NodeData } from '../editor-store'
afterEach(cleanup)
vi.mock('../api', () => ({ apiRequest: vi.fn(async () => ({ success: true, data: { items: [] } })) }))
vi.mock('../api/config', () => ({ getBackendBaseUrl: () => 'http://local.test' }))
it('keeps task authority out of user arguments and supports a result variable', async () => {
  const change = vi.fn()
  render(<ProjectDataConfig data={{ label: '项目数据', moduleType: 'project_data', operation: 'createRecord', arguments: {}, variableName: 'saved' } as NodeData} onChange={change} />)
  fireEvent.click(screen.getByRole('button', { name: '高级：直接编辑参数' }))
  const editor = screen.getByLabelText('操作参数（JSON，值可引用变量）')
  fireEvent.change(editor, { target: { value: '{"projectId":"forged"}' } }); fireEvent.blur(editor)
  expect((await screen.findByRole('alert')).textContent).toContain('不能在参数中覆盖')
  expect(change).toHaveBeenCalledWith('argumentsValid', false)
  expect(change.mock.calls.some(([key]) => key === 'arguments')).toBe(false)
  fireEvent.change(editor, { target: { value: '{"values":{"field":"{browser_result}"}}' } }); fireEvent.blur(editor)
  await waitFor(() => expect(change).toHaveBeenCalledWith('arguments', { values: { field: '{browser_result}' } }))
})

it('selects explicit schema fields and keeps the query free of write authority', async () => {
  const { apiRequest } = await import('../api')
  vi.mocked(apiRequest).mockImplementation(async path => ({ success: true, data: { items: path.endsWith('/fields') ? [{ ref: { projectId: 'project', tableId: 'table', datasetGeneration: 'generation', fieldId: 'field' }, name: '当前字段' }] : [], total: 0 } }) as never)
  const change = vi.fn()
  render(<ProjectDataConfig data={{ moduleType: 'project_data', operation: 'queryTableSchema', bindingProjectId: 'project', tableGrant: { tableId: 'table', datasetGeneration: 'generation', operations: ['queryTableSchema'], fieldIds: [], readPurposes: [] }, arguments: { tableId: 'table', datasetGeneration: 'generation', fieldIds: [] }, variableName: 'schema' } as unknown as NodeData} onChange={change} />)
  fireEvent.click(await screen.findByRole('checkbox', { name: /当前字段/ }))
  expect(change).toHaveBeenCalledWith('arguments', { tableId: 'table', datasetGeneration: 'generation', fieldIds: ['field'] })
  expect(change).toHaveBeenCalledWith('tableGrant', { tableId: 'table', datasetGeneration: 'generation', operations: ['queryTableSchema'], fieldIds: ['field'], readPurposes: [] })
  expect((screen.getByLabelText('结果变量') as HTMLInputElement).value).toBe('schema')
})

it.each(['addField', 'deleteField', 'previewFieldDeletion'])('keeps an old %s node visible but explains that runs no longer change table structure', operation => {
  // Remediation M2 R2-23.
  render(<ProjectDataConfig data={{ moduleType: 'project_data', operation, bindingProjectId: 'project', arguments: {}, variableName: 'x' } as unknown as NodeData} onChange={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('运行中不再修改表结构，请在项目「数据」页维护字段')
  const select = screen.getByLabelText('操作')
  fireEvent.keyDown(select, { key: 'ArrowDown' })
  expect(screen.queryByRole('option', { name: '添加字段' })).toBeNull()
  expect(screen.getByRole('option', { name: /（已停用）/ })).toHaveAttribute('aria-disabled', 'true')
})
