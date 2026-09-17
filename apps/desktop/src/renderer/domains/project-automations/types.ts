import type { components } from '../../shared/api/generated'
type Schema = components['schemas']
export type Automation = Schema['AutomationView']
export type AutomationWrite = Schema['AutomationWrite']
export type AutomationUpdate = Schema['AutomationUpdate']
export type AutomationPage = Schema['AutomationPage']
export type AutomationValidation = Schema['AutomationValidationView']
export type AutomationDirectoryQuery = {
  query: string
  page: number
  pageSize: number
  sort: 'name' | '-name' | 'updatedAt' | '-updatedAt'
}
