import { describe, expect, it } from 'vitest'
import { formatReference, INVALID_REFERENCE_LABEL, parseReferences, SENSITIVE_SAMPLE_MASK, type ReferenceContext } from '../dataReferences'

const context: ReferenceContext = {
  signature: { account: { label: '账号', fields: { email: { label: '邮箱', type: 'string', sample: 'a@b.com' }, secret: { label: '密码', sensitive: true, sample: 'hunter2' } } } },
  nodeOutputs: [{ nodeId: 'n1', key: 'url', name: '网址', label: '打开页面', type: 'string' }],
  variables: { 计数: { type: 'number', sample: '3' } },
  inputs: [{ inputId: 'in-1', alias: '订单', fields: [{ fieldId: 'f-1', alias: '金额', type: 'number' }] }],
}
const refs = (text: string) => parseReferences(text, context).filter(part => part.type === 'ref')

describe('parseReferences', () => {
  it('resolves signature references to group and field names with type and sample', () => {
    expect(refs('{input.account.email}')[0]).toMatchObject({ kind: 'input', display: '账号·邮箱', valid: true, dataType: 'string', sample: 'a@b.com' })
    expect(refs('${input.account}')[0]).toMatchObject({ display: '账号', valid: true })
  })

  it('resolves node output references to node title and output name', () => {
    expect(refs('{node.n1.url}')[0]).toMatchObject({ kind: 'node', display: '打开页面·网址', valid: true })
  })

  it('resolves legacy project input references and never shows internal ids when stale', () => {
    expect(refs("PROJECT_INPUTS['in-1']['values']['f-1']")[0]).toMatchObject({ kind: 'legacyInput', display: '订单·金额', valid: true })
    expect(refs("PROJECT_INPUTS['in-1']")[0]).toMatchObject({ display: '订单', valid: true })
    expect(refs("PROJECT_INPUTS['gone']['values']['x']")[0]).toMatchObject({ display: INVALID_REFERENCE_LABEL, valid: false })
    expect(refs("PROJECT_INPUTS['in-1']['values']['gone']")[0]).toMatchObject({ display: INVALID_REFERENCE_LABEL, valid: false })
    expect(formatReference("PROJECT_INPUTS['gone']", context)).not.toContain('gone')
  })

  it('marks unknown signature and node references invalid', () => {
    expect(refs('{input.nope.x}')[0]).toMatchObject({ display: INVALID_REFERENCE_LABEL, valid: false })
    expect(refs('{input.account.nope}')[0]).toMatchObject({ valid: false })
    expect(refs('{node.n9.url}')[0]).toMatchObject({ valid: false })
  })

  it('keeps legacy global variable names and treats names with spaces or dots as plain text', () => {
    expect(refs('{计数}')[0]).toMatchObject({ kind: 'variable', display: '计数', valid: true, dataType: 'number' })
    expect(refs('{未定义}')[0]).toMatchObject({ kind: 'variable', valid: false })
    expect(parseReferences('{my var} {a.b}', context)).toEqual([{ type: 'text', text: '{my var} {a.b}' }])
  })

  it('masks sensitive samples and keeps samples out of the display', () => {
    const part = refs('{input.account.secret}')[0]
    expect(part).toMatchObject({ sensitive: true, sample: SENSITIVE_SAMPLE_MASK, display: '账号·密码' })
    expect(JSON.stringify(part)).not.toContain('hunter2')
    expect(formatReference('{input.account.email}', context)).not.toContain('a@b.com')
  })

  it('handles consecutive and surrounding text', () => {
    expect(parseReferences('去 {node.n1.url}{input.account.email} 完', context).map(p => p.type)).toEqual(['text', 'ref', 'ref', 'text'])
    expect(formatReference('去 {node.n1.url}{input.account.email} 完', context)).toBe('去 打开页面·网址账号·邮箱 完')
  })

  it('treats nested braces, unclosed braces and escaped braces safely', () => {
    expect(formatReference('{{计数}}', context)).toBe('{计数}')
    expect(formatReference('{input.account.email', context)).toBe('{input.account.email')
    expect(formatReference('\\{计数\\}', context)).toBe('{计数}')
    expect(refs('\\{计数}')).toHaveLength(0)
  })

  it('works without context', () => {
    expect(parseReferences('{input.a.b}')[0]).toMatchObject({ valid: false })
    expect(parseReferences('')).toEqual([])
  })
})
