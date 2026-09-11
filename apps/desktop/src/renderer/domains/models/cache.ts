import type { QueryClient } from '@tanstack/react-query'
import { ApiClientError } from '../../shared/api/client'
import { modelKeys } from './model'

const staleCodes = new Set(['MODEL_PROVIDER_CHANGED', 'MODEL_PROVIDER_NOT_FOUND', 'MODEL_NOT_FOUND'])

// Reconcile lists after an external edit/deletion while preserving the open draft.
export function refreshAfterModelConflict(cache: QueryClient, instanceId: string, error: unknown): void {
  if (!(error instanceof ApiClientError) || !error.code || !staleCodes.has(error.code)) return
  void cache.invalidateQueries({ queryKey: modelKeys.providers(instanceId), exact: true })
  void cache.invalidateQueries({ queryKey: modelKeys.options(instanceId), exact: true })
}
