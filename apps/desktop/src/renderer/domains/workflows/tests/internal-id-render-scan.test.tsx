import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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

  it.skip('ProjectDataConfig shows no fieldId (fix: A7 write-back form)', () => {})
  it.skip('ProjectInputPanel candidate rows show no recordKey (A1 switches to the table display field; enable after A1 lands)', () => {})
  it.skip('navigation.ts shows no 数据代次 wording (later cleanup)', () => {})
  it.skip('DataTableSourcePanel shows no 数据代次 wording (later cleanup)', () => {})
})
