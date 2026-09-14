import { z } from 'zod'

const codePoints = (value: string) => [...value].length
const text120 = (label: string) => z.string().transform(value => value.trim()).pipe(z.string().min(1, `请输入${label}`).refine(value => codePoints(value) <= 120, `${label}最多 120 个字符`))
const jsonNumber = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/
const validNumber = (value: string) => value === '' || (jsonNumber.test(value) && Number.isFinite(Number(value)) && (!Number.isInteger(Number(value)) || Number.isSafeInteger(Number(value))))

export const fieldFormSchema = z.object({
  key: text120('字段键').refine(value => ![...value].some(character => /[\p{Cc}\p{Cs}]/u.test(character)), '字段键不能包含控制字符'),
  name: text120('字段名称'),
  type: z.enum(['string', 'number', 'boolean', 'date']),
  required: z.boolean(),
  minLength: z.string(),
  maxLength: z.string(),
  pattern: z.string(),
  minimum: z.string(),
  maximum: z.string(),
}).superRefine((value, context) => {
  if (value.type === 'string') {
    if (value.minLength !== '' && !/^\d+$/.test(value.minLength)) context.addIssue({ code: 'custom', path: ['minLength'], message: '请输入非负整数' })
    if (value.maxLength !== '' && !/^\d+$/.test(value.maxLength)) context.addIssue({ code: 'custom', path: ['maxLength'], message: '请输入非负整数' })
    if (codePoints(value.pattern) > 256) context.addIssue({ code: 'custom', path: ['pattern'], message: '正则表达式最多 256 个字符' })
    if (value.minLength !== '' && value.maxLength !== '' && Number(value.minLength) > Number(value.maxLength)) context.addIssue({ code: 'custom', path: ['maxLength'], message: '最大长度不能小于最小长度' })
  }
  if (value.type === 'number') {
    if (!validNumber(value.minimum)) context.addIssue({ code: 'custom', path: ['minimum'], message: '请输入有效数字' })
    if (!validNumber(value.maximum)) context.addIssue({ code: 'custom', path: ['maximum'], message: '请输入有效数字' })
    if (value.minimum !== '' && value.maximum !== '' && Number(value.minimum) > Number(value.maximum)) context.addIssue({ code: 'custom', path: ['maximum'], message: '最大值不能小于最小值' })
  }
})

export type FieldFormValues = z.input<typeof fieldFormSchema>
export const emptyFieldForm: FieldFormValues = { key: '', name: '', type: 'string', required: false, minLength: '', maxLength: '', pattern: '', minimum: '', maximum: '' }

export function fieldDefinition(values: FieldFormValues) {
  const parsed = fieldFormSchema.parse(values)
  const validation: Record<string, string | number> = {}
  if (parsed.type === 'string') {
    if (parsed.minLength !== '') validation.minLength = Number(parsed.minLength)
    if (parsed.maxLength !== '') validation.maxLength = Number(parsed.maxLength)
    if (parsed.pattern !== '') validation.pattern = parsed.pattern
  } else if (parsed.type === 'number') {
    if (parsed.minimum !== '') validation.minimum = Number(parsed.minimum)
    if (parsed.maximum !== '') validation.maximum = Number(parsed.maximum)
  }
  return { key: parsed.key, name: parsed.name, type: parsed.type, required: parsed.required, validation }
}
