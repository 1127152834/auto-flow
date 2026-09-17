import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { createProjectDataApi } from '../project-data/api'
import { createDataCatalogApi } from '../project-data/catalog-api'
import { createRecordsApi } from '../project-data/records-api'
import { recordDisplayLabel } from '../project-data/presentation'
import type { InputTableOption } from './components/InputPlanEditor'

type Schema = components['schemas']
export function createAutomationResourcesApi(client: StreamingApiClient, projectId: string) {
  return {
    workflows: (signal?: AbortSignal) => client.request<Schema['WorkflowCatalogList']>('/api/v1/workflows', { signal }),
    profiles: (signal?: AbortSignal) => client.request<Schema['ProfileList']>('/api/v1/profiles', { signal }),
    models: (signal?: AbortSignal) => client.request<Schema['ModelProviderListRead']>('/api/v1/model-providers', { signal }),
    proxies: (signal?: AbortSignal) => client.request<Schema['ProxyOptionsRead']>('/api/v1/proxy-options', { signal }),
    async tables(signal?: AbortSignal): Promise<InputTableOption[]> {
      const api = createProjectDataApi(client, projectId), tables: Schema['DataTableView'][] = []
      for (let page = 1; ; page++) {
        const result = await api.list({ query: '', page, pageSize: 200, sort: 'name' }, signal)
        tables.push(...result.items)
        if (tables.length >= result.total || !result.items.length) break
      }
      return Promise.all(tables.map(async table => {
        const api = createDataCatalogApi(client, { projectId, tableId: table.tableId, datasetGeneration: table.datasetGeneration })
        const [fields, statuses] = await Promise.all([api.fields(signal), api.statuses(signal)])
        return { id: table.tableId, name: table.name, datasetGeneration: table.datasetGeneration, identity: table.identity, fields: fields.items, statuses: statuses.items, slotDefinitions: table.slotDefinitions }
      }))
    },
    async records(table: InputTableOption, page: number, signal?: AbortSignal) {
      const result = await createRecordsApi(client, { projectId, tableId: table.id, datasetGeneration: table.datasetGeneration }).list({ page, pageSize: 200 }, signal)
      return { total: result.total, items: result.items.map(record => ({ label: recordDisplayLabel(table.identity ?? { mode: 'system' }, table.fields, record), ref: record.ref })) }
    },
  }
}
