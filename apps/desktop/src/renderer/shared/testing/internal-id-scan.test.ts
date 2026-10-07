import { describe, expect, it } from 'vitest'
import { findInternalIds } from './internal-id-scan'

const mount = (html: string) => { const el = document.createElement('div'); el.innerHTML = html; return el }
const UUID = '123e4567-e89b-12d3-a456-426614174000'

describe('findInternalIds', () => {
  it('finds uuids in text, attributes and input values', () => {
    const hits = findInternalIds(mount(`<p>记录 ${UUID}</p><button title="${UUID}">x</button><input value="${UUID}">`))
    expect(hits.map(hit => hit.rule)).toEqual(['uuid', 'uuid', 'uuid'])
    expect(hits[1].where).toBe('button[title]')
  })

  it('finds glossary terms and internal expressions', () => {
    const hits = findInternalIds(mount(`<span>数据集代次已更新</span><code aria-label="PROJECT_INPUTS['a']"></code>`))
    expect(hits).toEqual([
      expect.objectContaining({ rule: 'glossary', term: '数据集代次' }),
      expect.objectContaining({ rule: 'internal-expression' }),
    ])
  })

  it('returns nothing for clean content and ignores password values', () => {
    expect(findInternalIds(mount(`<p>账号·邮箱</p><input type="password" value="${UUID}">`))).toEqual([])
  })

  it('honours the allowlist and custom terms', () => {
    expect(findInternalIds(mount(`<p>${UUID}</p>`), { allowlist: [UUID] })).toEqual([])
    expect(findInternalIds(mount('<p>数据集代次</p>'), { allowlist: [/代次/] })).toEqual([])
    expect(findInternalIds(mount('<p>foo</p>'), { terms: ['foo'] })).toHaveLength(1)
  })
})
