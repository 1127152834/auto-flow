import { describe, expect, it } from 'vitest'
import { emptyRecordQuery, parseRecordQuery, recordQueryDraft, RecordQueryError } from './record-query'

const fields = [{ ref: { fieldId: 'name' }, type: 'string' as const }, { ref: { fieldId: 'amount' }, type: 'number' as const }, { ref: { fieldId: 'enabled' }, type: 'boolean' as const }, { ref: { fieldId: 'when' }, type: 'date' as const }]
const statuses = [{ statusId: 'open' }]

describe('record query draft', () => {
  it('round trips nested filters without encoding transport data', () => {
    const query = { filter: { type: 'all' as const, items: [{ type: 'not' as const, item: { type: 'status' as const, operator: 'eq', statusId: 'open' } }, { type: 'compare' as const, fieldId: 'name', operator: 'contains', value: ' x ' }] }, orderBy: [{ fieldId: 'amount', direction: 'desc' as const }] }
    expect(parseRecordQuery(recordQueryDraft(query), fields, statuses)).toEqual(query)
  })
  it('omits values for null operators and preserves precise dates', () => {
    const draft = recordQueryDraft({ filter: { type: 'compare', fieldId: 'when', operator: 'eq', value: { kind: 'date', precision: 'datetime', value: '2026-01-01T00:00:00.123456789', offset: '+08:00' } }, orderBy: [] })
    expect(parseRecordQuery(draft, fields, statuses).filter).toMatchObject({ value: { value: '2026-01-01T00:00:00.123456789', offset: '+08:00' } })
    draft.filter = { type: 'compare', fieldId: 'name', operator: 'isNull', value: { presence: 'value', text: 'ignored', boolean: false, precision: 'date', offset: '' } }
    expect(parseRecordQuery(draft, fields, statuses).filter).toEqual({ type: 'compare', fieldId: 'name', operator: 'isNull' })
  })
  it('rejects invalid drafts, empty any, stale references and duplicate sorts', () => {
    expect(() => parseRecordQuery({ filter: { type: 'any', items: [] }, orderBy: [] }, fields, statuses)).toThrow(RecordQueryError)
    expect(() => parseRecordQuery({ filter: { type: 'status', operator: 'eq', statusId: 'gone' }, orderBy: [] }, fields, statuses)).toThrow('所选状态已失效')
    expect(() => parseRecordQuery({ filter: { type: 'all', items: [] }, orderBy: [{ fieldId: 'name', direction: 'asc' }, { fieldId: 'name', direction: 'desc' }] }, fields, statuses)).toThrow('排序字段不能重复')
  })
  it('accepts the explicit match-all default', () => expect(parseRecordQuery(recordQueryDraft(emptyRecordQuery()), fields, statuses)).toEqual(emptyRecordQuery()))
  it('supports boolean and status null comparisons without stray values', () => {
    const query=parseRecordQuery({filter:{type:'all',items:[{type:'compare',fieldId:'enabled',operator:'eq',value:{presence:'value',text:'',boolean:false,precision:'date',offset:''}},{type:'status',operator:'isNull',statusId:'stale'}]},orderBy:[]},fields,statuses)
    expect(query.filter).toEqual({type:'all',items:[{type:'compare',fieldId:'enabled',operator:'eq',value:false},{type:'status',operator:'isNull'}]})
  })
  it('enforces the backend depth, leaf, group, and sort limits', () => {
    const leaf={type:'compare' as const,fieldId:'name',operator:'eq',value:{presence:'value' as const,text:'x',boolean:false,precision:'date' as const,offset:''}}
    expect(()=>parseRecordQuery({filter:{type:'all',items:Array.from({length:51},()=>leaf)},orderBy:[]},fields,statuses)).toThrow('最多 50')
    expect(()=>parseRecordQuery({filter:{type:'all',items:Array.from({length:9},()=>leaf)},orderBy:Array.from({length:9},(_,index)=>({systemField:'recordKey' as const,direction:(index%2?'asc':'desc') as 'asc'|'desc'}))},fields,statuses)).toThrow('最多 8')
    const tooDeep: Parameters<typeof parseRecordQuery>[0]={filter:{type:'not',item:{type:'not',item:{type:'not',item:{type:'not',item:{type:'not',item:leaf}}}}},orderBy:[]}
    expect(()=>parseRecordQuery(tooDeep,fields,statuses)).toThrow('最多 5 层')
  })
  it('checks the real base64url UTF-8 JSON size without encoding its output', () => {
    const huge={filter:{type:'compare' as const,fieldId:'name',operator:'eq',value:{presence:'value' as const,text:'文'.repeat(17000),boolean:false,precision:'date' as const,offset:''}},orderBy:[]}
    expect(()=>parseRecordQuery(huge,fields,statuses)).toThrow('超过 64 KiB')
  })
})
