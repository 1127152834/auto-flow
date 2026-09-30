import type { ProjectOperationPage } from './types'

/**
 * Local files the service could not remove. The delete operation keeps the
 * project in `deleting`, so the residue stays visible until a retry clears it.
 */
export function cleanupResidue(operation: ProjectOperationPage['items'][number] | null | undefined): string[] {
  const details = operation?.error?.details as { cleanup?: { residue?: unknown } } | null | undefined
  const residue = details?.cleanup?.residue
  return Array.isArray(residue) ? residue.filter((item): item is string => typeof item === 'string') : []
}

/**
 * Residue already recorded for a project. Operations are listed newest first and
 * a `deleting` project accepts no new operation besides another delete, so the
 * newest `deleteProject` entry carries the latest cleanup evidence.
 */
export function reportedCleanupResidue(page: ProjectOperationPage | undefined): string[] {
  return cleanupResidue(page?.items.find(item => item.kind === 'deleteProject'))
}
