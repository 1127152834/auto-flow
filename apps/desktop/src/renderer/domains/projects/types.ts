import type { DataTableTab } from '../project-data/types'
import type { RecordKey } from '../project-data/records-api'
import type { components } from '../../shared/api/generated'

export type ProjectView = components['schemas']['ProjectView']
export type ProjectSummary = components['schemas']['ProjectSummary']
export type ProjectOverview = components['schemas']['ProjectOverview']
export type ProjectPage = components['schemas']['ProjectPage']
export type ProjectOperationView = components['schemas']['ProjectOperationView']
export type ProjectOperationPage = components['schemas']['ProjectOperationPage']
export type ProjectOpenResult = components['schemas']['ProjectOpenResult']
export type ProjectCreate = components['schemas']['ProjectCreate']
export type ProjectPatch = components['schemas']['ProjectPatch']

export type ProjectTab = 'overview' | 'automations' | 'runs' | 'statistics' | 'data' | 'environments'
export type RecordLocation = { mode: 'create' } | { mode: 'detail' | 'edit'; datasetGeneration: string; recordKey: RecordKey }
export type ProjectRoute = { projectId?: string; tab: ProjectTab; tableId?: string; dataTab?: DataTableTab; record?: RecordLocation; automationId?: string; automationCreate?: boolean; runView?: 'batches' | 'tasks' | 'manual'; batchId?: string; taskId?: string; manualItemId?: string; taskTab?: 'logs' | 'io' | 'evidence'; environmentId?: string }
export type ProjectLifecycleFilter = 'active' | 'archived' | 'all'
export type ProjectSort = 'name' | '-name' | 'updatedAt' | '-updatedAt' | 'lastOpenedAt' | '-lastOpenedAt'

export type ProjectListConditions = {
  query: string
  lifecycle: ProjectLifecycleFilter
  sort: ProjectSort
  page: number
  pageSize: number
}
