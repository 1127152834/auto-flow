import { z } from 'zod'

const codePoints = (value: string) => [...value].length
const maxSafeOrder = Number.MAX_SAFE_INTEGER

export const statusFormSchema = z.object({
  name: z.string().transform(value => value.trim()).pipe(
    z.string().min(1, '请输入状态名称').refine(value => codePoints(value) <= 120, '状态名称最多 120 个字符'),
  ),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/, '请输入 #RRGGBB 格式的颜色').transform(value => value.toLowerCase()),
  order: z.number().int('顺序必须是整数').min(0, '顺序不能小于 0').max(maxSafeOrder, '顺序超出安全范围'),
})

export type StatusFormValues = z.input<typeof statusFormSchema>
export type CanonicalStatusFormValues = z.output<typeof statusFormSchema>
export const emptyStatusForm: StatusFormValues = { name: '', color: '#a86f4c', order: 0 }
