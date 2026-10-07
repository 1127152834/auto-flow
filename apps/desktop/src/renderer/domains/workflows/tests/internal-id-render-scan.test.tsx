import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ProjectDataConfig } from '../components/config-panels/ProjectDataConfig'
import type { NodeData } from '../editor-store'
const request = vi.hoisted(() => vi.fn())
vi.mock('../api', () => ({ apiRequest: request }))
vi.mock('../api/config', () => ({ getBackendBaseUrl: () => 'http://local.test' }))
import { findInternalIds } from '../../../shared/testing/internal-id-scan'

// AC5-03 skeleton: each skipped case names a known leak and the slice that fixes it; enable it there.
describe('internal id render scan', () => {
  it('flags a uuid shown in a record row', () => {
    const { container } = render(<table><tbody><tr><td>选择记录 123e4567-e89b-12d3-a456-426614174000</td></tr></tbody></table>)
    expect(findInternalIds(container)).toHaveLength(1)
  })

  it('flags a banned term in a hint', () => {
    const { container } = render(<p title="数据集代次已变化">提示</p>)
    expect(findInternalIds(container)).toEqual([expect.objectContaining({ rule: 'glossary', where: 'p[title]' })])
  })

  it('passes business labels', () => {
    const { container } = render(<p>账号·邮箱</p>)
    expect(findInternalIds(container)).toEqual([])
  })

  it.each(['updateRecord', 'createRecord', 'queryRecords', 'readRecord'])('ProjectDataConfig %s shows no field or table id', async operation => {
    const uuid = (n: number) => `123e4567-e89b-12d3-a456-42661417400${n}`
    const ref = { projectId: uuid(7), tableId: uuid(8), datasetGeneration: uuid(9), fieldId: uuid(1) }
    const field = { key: 'result', name: '结果', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1, ref }
    request.mockImplementation(async (path: string) => {
      if (path.startsWith('/v1/projects?pageSize=')) return { success: true, data: { items: [{ projectId: uuid(7), name: '当前项目' }], total: 1 } }
      if (path.includes('/tables?')) return { success: true, data: { items: [{ projectId: uuid(7), tableId: uuid(8), datasetGeneration: uuid(9), name: '业务记录', tableRevision: 1 }], total: 1 } }
      if (path.endsWith('/fields')) return { success: true, data: { items: [field] } }
      return { success: true, data: { items: [] } }
    })
    const data = { moduleType: 'project_data', operation, bindingProjectId: uuid(7), variableName: 'saved',
      tableGrant: { tableId: uuid(8), datasetGeneration: uuid(9), operations: [operation], fieldIds: [uuid(1)], readPurposes: ['condition'] },
      arguments: { tableId: uuid(8), datasetGeneration: uuid(9), changes: { [uuid(1)]: '成功' }, values: { [uuid(1)]: '成功' }, fieldIds: [uuid(1)], filter: { type: 'all', items: [{ type: 'compare', fieldId: uuid(1), operator: 'eq', value: 'x' }] } } } as unknown as NodeData
    const { container } = render(<ProjectDataConfig data={data} onChange={vi.fn()} />)
    await screen.findAllByText('结果')
    expect(findInternalIds(container)).toEqual([])
  })
  it.skip('navigation.ts shows no 数据代次 wording (later cleanup)', () => {})
  it.skip('DataTableSourcePanel shows no 数据代次 wording (later cleanup)', () => {})
})
