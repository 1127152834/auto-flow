import { useQuery } from '@tanstack/react-query'
import type { ProjectsApi } from './api'
import type { ProjectListConditions } from './types'

export const projectKeys = {
  directory: (workspaceKey: string, instanceId: string, conditions: ProjectListConditions) => [workspaceKey, instanceId, 'projects', conditions] as const,
  detail: (workspaceKey: string, instanceId: string, projectId: string) => [workspaceKey, instanceId, 'project', projectId] as const,
  overview: (workspaceKey: string, instanceId: string, projectId: string) => [workspaceKey, instanceId, 'project-overview', projectId] as const,
}

export function useProjectDirectory(api: ProjectsApi, workspaceKey: string, instanceId: string, conditions: ProjectListConditions, enabled = true) {
  return useQuery({ queryKey: projectKeys.directory(workspaceKey, instanceId, conditions), queryFn: ({ signal }) => api.list(conditions, signal), enabled })
}

export function useProject(api: ProjectsApi, workspaceKey: string, instanceId: string, projectId?: string) {
  return useQuery({ queryKey: projectKeys.detail(workspaceKey, instanceId, projectId ?? ''), queryFn: ({ signal }) => api.get(projectId!, signal), enabled: Boolean(projectId) })
}

export function useProjectOverview(api: ProjectsApi, workspaceKey: string, instanceId: string, projectId?: string) {
  return useQuery({ queryKey: projectKeys.overview(workspaceKey, instanceId, projectId ?? ''), queryFn: ({ signal }) => api.overview(projectId!, signal), enabled: Boolean(projectId) })
}
