import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import type { CatalogScope } from './catalog-api'
import { createDataCommand, type DataCommandPolicy } from './data-command'

type Schema = components['schemas']
export type SchemaCandidate = Schema['DataSchemaCandidate']
export type SchemaImpact = Schema['DataSchemaImpact']
export type SchemaResult = Schema['DataSchemaResult']

export function createSchemaApi(client: StreamingApiClient, scope: CatalogScope) {
  const base = `/api/v1/projects/${encodeURIComponent(scope.projectId)}/tables/${encodeURIComponent(scope.tableId)}/schema`
  const command = createDataCommand(client, scope.projectId)
  const recover = ({ resource, result }: Schema['ProjectOperationView']): SchemaResult => {
    if (resource.type !== 'table' || resource.projectId !== scope.projectId || resource.tableId !== scope.tableId
      || !result || !('action' in result) || result.action !== 'saveSchema'
      || result.datasetGeneration !== scope.datasetGeneration || !Number.isSafeInteger(result.tableRevision) || result.tableRevision < 1
      || !Array.isArray(result.fields) || !result.fields.every(field => field.ref.projectId === scope.projectId && field.ref.tableId === scope.tableId && field.ref.datasetGeneration === scope.datasetGeneration)) {
      throw new Error('字段保存结果与当前数据表不一致')
    }
    return result
  }
  return {
    preview: (candidate: SchemaCandidate, signal?: AbortSignal) => client.request<SchemaImpact>(`${base}/preview`, { method: 'POST', body: candidate, signal }),
    commit: (body: Schema['DataSchemaCommit'], key: string, resume = false, policy?: DataCommandPolicy) => command(base, 'POST', body, key, 'saveTableSchema', resume, recover, policy),
  }
}
