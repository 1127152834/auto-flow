import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { createOperationCommand } from './operation-command'
import type { createProjectFileClient } from './project-file-client'

type Operation = components['schemas']['ProjectOperationView']
export type ExcelImportRequest = components['schemas']['ExcelTableImportCreate']
export type ExcelReplaceRequest = components['schemas']['ExcelTableReplace']
export type ExcelReplaceImpact = components['schemas']['ExcelReplaceImpact']
export type ExcelInspection = components['schemas']['ExcelInspectionView']
export type ExcelExportRequest = components['schemas']['ExcelExportCreate']

/** File grants authorize new commands. Durable results remain queryable after a grant expires. */
export function createExcelApi(client: StreamingApiClient, files: Pick<ReturnType<typeof createProjectFileClient>, 'request'>, projectId: string) {
  const transport: Pick<StreamingApiClient, 'request'> = {
    request: (path, init) => init?.method === 'POST' ? files.request(path, init) : client.request(path, init),
  }
  const command = createOperationCommand(transport, projectId)
  const ordinaryCommand = createOperationCommand(client, projectId)
  const inspectionOperation = (operation: Operation) => {
    if (operation.resource.type !== 'project' || operation.resource.projectId !== projectId) throw new Error('文件检查结果与当前项目不一致')
    return operation
  }
  const imported = (operation: Operation, tableId?: string) => {
    const resource = operation.resource
    if ((resource.type !== 'table' && resource.type !== 'project') || resource.projectId !== projectId || (tableId ? resource.type !== 'table' || resource.tableId !== tableId : resource.type !== 'project' && resource.type !== 'table')) throw new Error('导入操作与当前数据表不一致')
    if (operation.status === 'succeeded') {
      const result = operation.result
      if (!result || !('importedRecordCount' in result) || resource.type !== 'table' || result.table.projectId !== projectId || result.table.tableId !== resource.tableId) throw new Error('导入结果与当前数据表不一致')
    }
    return operation
  }
  const base = `/api/v1/projects/${encodeURIComponent(projectId)}`
  const exported = (operation: Operation, tableId: string) => {
    if (operation.resource.type !== 'table' || operation.resource.projectId !== projectId || operation.resource.tableId !== tableId) throw new Error('导出操作与当前数据表不一致')
    if (operation.status === 'succeeded' && (!operation.result || !('sha256' in operation.result))) throw new Error('导出结果与当前数据表不一致')
    return operation
  }
  const reconciled = (operation: Operation, tableId: string, targetOperationId: string, expectedStatusRevision: number) => {
    if (operation.resource.type !== 'table' || operation.resource.projectId !== projectId || operation.resource.tableId !== tableId) throw new Error('核验操作与当前数据表不一致')
    const result = operation.result
    if (!result || !('targetOperationId' in result) || result.targetOperationId !== targetOperationId) throw new Error('核验结果与原导出操作不一致')
    if (!terminalOperation(operation) && (!('expectedTargetRevision' in result) || result.expectedTargetRevision !== expectedStatusRevision + 1 || result.status !== 'reconciling')) throw new Error('核验结果与原导出版本不一致')
    return operation
  }
  const terminalOperation = (operation: Operation) => operation.status === 'succeeded' || operation.status === 'failed'
  return {
    startImport: async (body: ExcelImportRequest, key: string, current: () => boolean) => imported(await command.submit(`${base}/table-imports/excel`, body, key, 'importExcel', current)),
    replace: async (tableId: string, body: ExcelReplaceRequest, key: string, current: () => boolean) => imported(await command.submit(`${base}/tables/${encodeURIComponent(tableId)}/imports/excel`, body, key, 'importExcel', current), tableId),
    lookupImport: async (key: string, current: () => boolean, tableId?: string) => imported(await command.lookup(key, 'importExcel', current), tableId),
    replaceImpact: (tableId: string, signal?: AbortSignal) => client.request<ExcelReplaceImpact>(`${base}/tables/${encodeURIComponent(tableId)}/imports/excel/impact`, { method: 'POST', signal }),
    inspect: async (selectionToken: string, key: string, current: () => boolean) => inspectionOperation(await command.submit(
      `/api/v1/projects/${encodeURIComponent(projectId)}/table-imports/excel/inspect`, { selectionToken }, key, 'inspectExcel', current,
    )),
    lookupInspection: async (key: string, current: () => boolean, signal?: AbortSignal) => inspectionOperation(await command.lookup(key, 'inspectExcel', current, signal)),
    startExport: async (tableId: string, body: ExcelExportRequest, key: string, current: () => boolean) => exported(await command.submit(`${base}/tables/${encodeURIComponent(tableId)}/exports/xlsx`, body, key, 'exportXlsx', current), tableId),
    lookupExport: async (tableId: string, key: string, current: () => boolean, signal?: AbortSignal) => exported(await command.lookup(key, 'exportXlsx', current, signal), tableId),
    reconcileExport: async (tableId: string, operationId: string, expectedStatusRevision: number, key: string, current: () => boolean) => reconciled(await ordinaryCommand.submit(`${base}/operations/${encodeURIComponent(operationId)}/reconcile`, { expectedStatusRevision }, key, 'reconcileOperation', current), tableId, operationId, expectedStatusRevision),
    lookupReconcile: async (tableId: string, targetOperationId: string, expectedStatusRevision: number, key: string, current: () => boolean, signal?: AbortSignal) => reconciled(await ordinaryCommand.lookup(key, 'reconcileOperation', current, signal), tableId, targetOperationId, expectedStatusRevision),
  }
}
export type ExcelApi = ReturnType<typeof createExcelApi>
