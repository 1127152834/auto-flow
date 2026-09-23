import { setStudioTransport, type StudioTransport } from './transport'
import type { StudioOpenContext } from '../../../../shared/automation-studio'

let backendOrigin: string | undefined

/** Compose before mounting Studio; disconnect existing event clients before replacing. */
export function configureStudioConnection(origin: string, transport: StudioTransport): () => void {
  const normalizedOrigin = normalizeStudioOrigin(origin)
  const previous = backendOrigin
  backendOrigin = normalizedOrigin
  const restoreTransport = setStudioTransport(transport)
  return () => { backendOrigin = previous; restoreTransport() }
}

/** AutoFlow owns connection selection; no source-project discovery or credentials. */
export const getBackendBaseUrl = () => {
  if (!backendOrigin) throw new Error('Studio connection has not been configured')
  return backendOrigin
}
export const getBackendPort = () => new URL(getBackendBaseUrl()).port
export const getFrontendPort = () => location.port
export const setBackendPort = (_port: number | string) => { throw new Error('Studio connection is managed by AutoFlow') }
export const preloadConfig = async () => { getBackendBaseUrl() }

export function getStudioOpenContext(): StudioOpenContext {
  const params = new URLSearchParams(location.search)
  const context: StudioOpenContext = {}
  for (const key of ['workspaceKey', 'instanceId', 'projectId', 'workflowId'] as const) {
    const value = params.get(key)
    if (value) context[key] = value
  }
  return context
}

/** Resource overrides belong to a workspace/project, and survive its service reconnect. */
export function getStudioResourceScope(): string | null {
  const {projectId, workspaceKey} = getStudioOpenContext()
  return projectId ? JSON.stringify([workspaceKey ?? getBackendBaseUrl(), projectId]) : null
}

/** Keep document, run, control and event requests on the registered window's project. */
export function scopeStudioUrl(url: string, projectId = getStudioOpenContext().projectId): string {
  if (!projectId) return url
  const scoped = new URL(url)
  if (/^\/api\/(?:workflows|workflow-runs|events|browser|element-picker|recorder|ai-assistant)(?:\/|$)/.test(scoped.pathname)) {
    scoped.searchParams.set('projectId', projectId)
    return scoped.toString()
  }
  return url
}

/** Shared validation for connection composition and authenticated HTTP transport. */
export function normalizeStudioOrigin(origin: string): string {
  const url = new URL(origin)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Studio connection requires an HTTP origin without credentials or path')
  }
  return url.origin
}
