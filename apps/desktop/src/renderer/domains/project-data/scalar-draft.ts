import type { components } from '../../shared/api/generated'

type CellScalar = components['schemas']['DataCellWrite']['value']
export type Scalar = CellScalar
export type ScalarDraft = {
  presence: 'missing' | 'null' | 'value'
  text: string
  boolean: boolean
  precision: 'date' | 'datetime'
  offset: string
}

const blank = (): ScalarDraft => ({ presence: 'missing', text: '', boolean: false, precision: 'date', offset: '' })

export function scalarDraft(value: CellScalar | undefined): ScalarDraft {
  const draft = blank()
  if (value === undefined) return draft
  if (value === null) return { ...draft, presence: 'null' }
  if (typeof value === 'boolean') return { ...draft, presence: 'value', boolean: value }
  if (typeof value === 'string' || typeof value === 'number') return { ...draft, presence: 'value', text: String(value) }
  return { ...draft, presence: 'value', text: value.value, precision: value.precision, offset: value.offset ?? '' }
}

const unicodeIsValid = (value: string) => {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(++index)
      if (!(next >= 0xdc00 && next <= 0xdfff)) return false
    } else if (code >= 0xdc00 && code <= 0xdfff) return false
  }
  return true
}

const daysInMonth = (year: number, month: number) => {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28
  return [4, 6, 9, 11].includes(month) ? 30 : 31
}

function validDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const year = Number(match[1]); const month = Number(match[2]); const day = Number(match[3])
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= daysInMonth(year, month)
}

const DATETIME = /^(\d{4}-\d{2}-\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?$/
const OFFSET = /^(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/

export function parseScalarDraft(type: 'string' | 'number' | 'boolean' | 'date', draft: ScalarDraft): Scalar | undefined {
  if (draft.presence === 'missing') return undefined
  if (draft.presence === 'null') return null
  if (type === 'string') {
    if (!unicodeIsValid(draft.text)) throw new Error('文本包含无效 Unicode 字符')
    return draft.text
  }
  if (type === 'boolean') return draft.boolean
  if (type === 'number') {
    if (!/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(draft.text)) throw new Error('请输入有效数字')
    const value = Number(draft.text)
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) throw new Error('数字超出安全范围')
    return value
  }
  if (draft.precision === 'date') {
    if (!validDate(draft.text)) throw new Error('请输入有效日期')
    return { kind: 'date', precision: 'date', value: draft.text, offset: null }
  }
  const match = DATETIME.exec(draft.text)
  if (!match || !validDate(match[1])) throw new Error('请输入有效日期时间')
  if (draft.offset && !OFFSET.test(draft.offset)) throw new Error('请输入有效时区偏移')
  return { kind: 'date', precision: 'datetime', value: draft.text, offset: draft.offset || null }
}
