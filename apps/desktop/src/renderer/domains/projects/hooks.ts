import { useQueries, useQuery } from '@tanstack/react-query'
import type { ProjectsApi } from './api'
import { reportedCleanupResidue } from './cleanup-residue'
import type { ProjectListConditions } from './types'

export const projectKeys = {
  directory: (workspaceKey: string, instanceId: string, conditions: ProjectListConditions) => [workspaceKey, instanceId, 'projects', conditions] as const,
  detail: (workspaceKey: string, instanceId: string, projectId: string) => [workspaceKey, instanceId, 'project', projectId] as const,
  overview: (workspaceKey: string, instanceId: string, projectId: string) => [workspaceKey, instanceId, 'project-overview', projectId] as const,
  residue: (workspaceKey: string, instanceId: string, projectId: string) => [workspaceKey, instanceId, 'project-lifecycle-residue', projectId] as const,
}

export function useProjectDirectory(api: ProjectsApi, workspaceKey: string, instanceId: string, conditions: ProjectListConditions, enabled = true) {
  return useQuery({ queryKey: projectKeys.directory(workspaceKey, instanceId, conditions), queryFn: ({ signal }) => api.list(conditions, signal), enabled })
}

export function useProject(api: ProjectsApi, workspaceKey: string, instanceId: string, projectId?: string) {
  return useQuery({ queryKey: projectKeys.detail(workspaceKey, instanceId, projectId ?? ''), queryFn: ({ signal }) => api.get(projectId!, signal), enabled: Boolean(projectId) })
}

export function useProjectOverview(api: ProjectsApi, workspaceKey: string, instanceId: string, projectId?: string, visible = true) {
  return useQuery({ queryKey: projectKeys.overview(workspaceKey, instanceId, projectId ?? ''), queryFn: ({ signal }) => api.overview(projectId!, signal), enabled: Boolean(projectId) && visible })
}

/**
 * Cleanup residue per project, only asked for projects that are still deleting.
 * A project in `deleting` keeps answering this read so the residue stays
 * visible until a retry clears it (PM8 spec §3 “残留可见”).
 */
export function useProjectCleanupResidues(api: ProjectsApi, workspaceKey: string, instanceId: string, projectIds: string[]) {
  const ids = [...new Set(projectIds)].filter(Boolean)
  const queries = useQueries({
    queries: ids.map(projectId => ({
      queryKey: projectKeys.residue(workspaceKey, instanceId, projectId),
      queryFn: ({ signal }: { signal: AbortSignal }) => api.operations(projectId, signal),
    })),
  })
  const residues: Record<string, string[]> = {}
  ids.forEach((projectId, index) => {
    const residue = reportedCleanupResidue(queries[index]?.data)
    if (residue.length) residues[projectId] = residue
  })
  return residues
}
