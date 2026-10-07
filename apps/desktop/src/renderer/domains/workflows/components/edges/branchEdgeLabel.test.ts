import { describe, expect, it } from 'vitest'
import { branchEdgeLabel } from './branchEdgeLabel'

describe('branchEdgeLabel', () => {
  it.each([['true', '是'], ['false', '否'], ['loop', '循环'], ['done', '完成'], ['error', '出错时'], ['path1', '路径1'], ['path2', '路径2']])('%s 连线显示 %s', (sourceHandle, label) => {
    expect(branchEdgeLabel({ sourceHandle }).label).toBe(label)
  })

  it('字号不小于 11px，背景可读', () => {
    const props = branchEdgeLabel({ sourceHandle: 'true' })
    expect(props.labelStyle?.fontSize).toBeGreaterThanOrEqual(11)
    expect(props.labelBgStyle?.fillOpacity).toBeGreaterThanOrEqual(0.9)
  })

  it('普通连线、未知出口、已有文字的连线不加标签', () => {
    expect(branchEdgeLabel({})).toEqual({})
    expect(branchEdgeLabel({ sourceHandle: null })).toEqual({})
    expect(branchEdgeLabel({ sourceHandle: 'other' })).toEqual({})
    expect(branchEdgeLabel({ sourceHandle: 'true', label: '自定义' })).toEqual({})
  })
})
