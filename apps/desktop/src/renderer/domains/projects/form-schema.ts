import { z } from 'zod'
import type { ProjectCreate, ProjectPatch, ProjectView } from './types'

const codePointLength = (value: string) => [...value].length

export const projectFormSchema = z.object({
  name: z.string().transform(value => value.trim()).pipe(
    z.string().min(1, '请输入项目名称').refine(value => codePointLength(value) <= 36, '项目名称最多 36 个字符'),
  ),
  description: z.string().refine(value => codePointLength(value) <= 120, '项目描述最多 120 个字符'),
})

export type ProjectFormValues = z.input<typeof projectFormSchema>

export const emptyProjectForm: ProjectFormValues = { name: '', description: '' }

export function projectToForm(project: ProjectView): ProjectFormValues {
  return { name: project.name, description: project.description }
}

export function toProjectCreate(values: ProjectFormValues): ProjectCreate {
  const parsed = projectFormSchema.parse(values)
  return { name: parsed.name, description: parsed.description }
}

export function toProjectPatch(values: ProjectFormValues, expectedManagementRevision: number): ProjectPatch {
  return { ...toProjectCreate(values), expectedManagementRevision }
}
