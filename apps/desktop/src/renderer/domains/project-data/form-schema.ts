import { z } from 'zod'

const codePoints = (value: string) => [...value].length

export const dataTableFormSchema = z.object({
  name: z.string().transform(value => value.trim()).pipe(
    z.string().min(1, '请输入数据表名称').refine(value => codePoints(value) <= 120, '数据表名称最多 120 个字符'),
  ),
  description: z.string().refine(value => codePoints(value) <= 1000, '数据表描述最多 1000 个字符'),
})

export type DataTableFormValues = z.input<typeof dataTableFormSchema>
export const emptyDataTableForm: DataTableFormValues = { name: '', description: '' }
