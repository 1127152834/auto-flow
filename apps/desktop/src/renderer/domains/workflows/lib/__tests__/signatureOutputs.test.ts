import { describe, expect, it } from 'vitest'
import { describeFlowOutputs } from '../signatureOutputs'

const node = (id: string, data: Record<string, unknown>) => ({ id, data })

describe('describeFlowOutputs', () => {
  it('lists End results and record write-backs in business language', () => {
    const items = describeFlowOutputs([
      node('a', { moduleType: 'project_end', label: '结束', businessResult: 'failed', retainEnvironment: true }),
      node('b', { moduleType: 'project_data', label: '写回状态', operation: 'setRecordStatus' }),
      node('c', { moduleType: 'project_data', label: '读取', operation: 'readRecord' }),
      node('d', { moduleType: 'click_element', label: '点击' }),
    ])
    expect(items.map(item => item.kind)).toEqual(['result', 'write'])
    expect(items[0]).toMatchObject({ node: '结束', text: '业务结果：失败；保留当前登录状态' })
    expect(items[1]).toMatchObject({ node: '写回状态', text: '设置记录状态' })
  })
  it('is empty when the flow has no End or write-back node', () => {
    expect(describeFlowOutputs([node('d', { moduleType: 'click_element' })])).toEqual([])
  })
})
