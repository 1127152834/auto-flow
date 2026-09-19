import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { ProjectCreate, ProjectLifecycleImpact, ProjectListConditions, ProjectOpenResult, ProjectOperationPage, ProjectOperationView, ProjectOverview, ProjectPage, ProjectPatch, ProjectView } from './types'

export type ProjectLifecycleAction = 'archive' | 'delete'

export type ProjectsApi = ReturnType<typeof createProjectsApi>

export class ProjectCommandUncertain extends Error {
  constructor(readonly cause: unknown) {
    super('上次保存结果尚未确认，请核对保存结果。')
    this.name = 'ProjectCommandUncertain'
  }
}

function encoded(value: string) { return encodeURIComponent(value) }

export function isDefinitiveProjectFailure(error: unknown): boolean {
  return error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408
}

function outcomeUnknown(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return false
  return !isDefinitiveProjectFailure(error)
}

function operationResult(operation: ProjectOperationView): ProjectView {
  if (operation.status !== 'succeeded' || operation.resource.type !== 'project'
    || !['createProject', 'updateProject'].includes(operation.kind)
    || !operation.result || !('managementRevision' in operation.result) || 'automationId' in operation.result) {
    throw new Error('未找到匹配的项目保存结果')
  }
  return operation.result
}

function operationNotFound(error: unknown): boolean {
  return error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND'
}

export function createProjectsApi(client: StreamingApiClient, createKey: () => string = () => crypto.randomUUID()) {
  const workspaceOperationByKey = (key: string) => client.request<ProjectOperationView>(`/api/v1/workspace/operations/by-idempotency-key/${encoded(key)}`)
  const projectOperationByKey = (projectId: string, key: string) => client.request<ProjectOperationView>(`/api/v1/projects/${encoded(projectId)}/operations/by-idempotency-key/${encoded(key)}`)

  async function recover(submit: () => Promise<ProjectView>, lookup: () => Promise<ProjectOperationView>): Promise<ProjectView> {
    try {
      return operationResult(await lookup())
    } catch (lookupError) {
      if (!operationNotFound(lookupError)) throw new ProjectCommandUncertain(lookupError)
      try {
        return await submit()
      } catch (retryError) {
        if (isDefinitiveProjectFailure(retryError)) throw retryError
        throw new ProjectCommandUncertain(retryError)
      }
    }
  }

  async function create(body: ProjectCreate, key = createKey()): Promise<ProjectView> {
    const submit = () => client.request<ProjectView>('/api/v1/projects', { method: 'POST', headers: { 'Idempotency-Key': key }, body })
    try {
      return await submit()
    } catch (error) {
      if (!outcomeUnknown(error)) throw error
      return recover(submit, () => workspaceOperationByKey(key))
    }
  }

  async function resumeCreate(body: ProjectCreate, key: string): Promise<ProjectView> {
    const submit = () => client.request<ProjectView>('/api/v1/projects', { method: 'POST', headers: { 'Idempotency-Key': key }, body })
    return recover(submit, () => workspaceOperationByKey(key))
  }

  async function resumePatch(projectId: string, body: ProjectPatch, key: string): Promise<ProjectView> {
    const submit = () => client.request<ProjectView>(`/api/v1/projects/${encoded(projectId)}`, { method: 'PATCH', headers: { 'Idempotency-Key': key }, body })
    return recover(submit, () => projectOperationByKey(projectId, key))
  }

  async function apiPatch(projectId: string, body: ProjectPatch, key = createKey()): Promise<ProjectView> {
    const submit = () => client.request<ProjectView>(`/api/v1/projects/${encoded(projectId)}`, { method: 'PATCH', headers: { 'Idempotency-Key': key }, body })
    try { return await submit() } catch (error) {
      if (!outcomeUnknown(error)) throw error
      return recover(submit, () => projectOperationByKey(projectId, key))
    }
  }

  async function accepted(submit: () => Promise<{ operation: ProjectOperationView }>, lookup: () => Promise<ProjectOperationView>): Promise<ProjectOperationView> {
    try { return (await submit()).operation } catch (error) {
      if (!outcomeUnknown(error)) throw error
      try { return await lookup() } catch (lookupError) {
        if (operationNotFound(lookupError)) throw new ProjectCommandUncertain(error)
        throw new ProjectCommandUncertain(lookupError)
      }
    }
  }

  const archive = (projectId: string, body: { impactRevision: number; expectedManagementRevision: number }, key = createKey()) => accepted(
    () => client.request<{ operation: ProjectOperationView }>(`/api/v1/projects/${encoded(projectId)}/archive`, { method: 'POST', headers: { 'Idempotency-Key': key }, body }),
    () => projectOperationByKey(projectId, key),
  )

  const restore = (projectId: string, body: { expectedManagementRevision: number }, key = createKey()) => accepted(
    () => client.request<{ operation: ProjectOperationView }>(`/api/v1/projects/${encoded(projectId)}/restore`, { method: 'POST', headers: { 'Idempotency-Key': key }, body }),
    () => projectOperationByKey(projectId, key),
  )

  // A deleted project answers 404 on every project-scoped read, so the command
  // identity survives only through the workspace-scoped lookup.
  const remove = (projectId: string, body: { confirmationName: string; impactRevision: number; expectedManagementRevision: number }, key = createKey()) => accepted(
    () => client.request<{ operation: ProjectOperationView }>(`/api/v1/projects/${encoded(projectId)}`, { method: 'DELETE', headers: { 'Idempotency-Key': key }, body }),
    () => workspaceOperationByKey(key),
  )

  return {
    list: (conditions: ProjectListConditions, signal?: AbortSignal) => {
      const lifecycle = conditions.lifecycle === 'all' ? '' : `&lifecycleState=${conditions.lifecycle}`
      const params = `q=${encoded(conditions.query)}${lifecycle}&sort=${encoded(conditions.sort)}&page=${conditions.page}&pageSize=${conditions.pageSize}`
      return client.request<ProjectPage>(`/api/v1/projects?${params}`, { signal })
    },
    get: (projectId: string, signal?: AbortSignal) => client.request<ProjectView>(`/api/v1/projects/${encoded(projectId)}`, { signal }),
    create,
    resumeCreate,
    patch: apiPatch,
    resumePatch,
    open: (projectId: string) => client.request<ProjectOpenResult>(`/api/v1/projects/${encoded(projectId)}/open`, { method: 'POST' }),
    overview: (projectId: string, signal?: AbortSignal) => client.request<ProjectOverview>(`/api/v1/projects/${encoded(projectId)}/overview`, { signal }),
    operations: (projectId: string, signal?: AbortSignal) => client.request<ProjectOperationPage>(`/api/v1/projects/${encoded(projectId)}/operations`, { signal }),
    lifecycleImpact: (projectId: string, action: ProjectLifecycleAction, signal?: AbortSignal) => client.request<ProjectLifecycleImpact>(`/api/v1/projects/${encoded(projectId)}/lifecycle-impact?action=${action}`, { signal }),
    archive,
    restore,
    remove,
    workspaceOperationByKey,
    projectOperationByKey,
  }
}
