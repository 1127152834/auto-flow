import { useQuery } from '@tanstack/react-query'
import type { ApiClient } from '../../../shared/api/client'
import { getDashboard } from '../api'

export function useDashboard(client: ApiClient) {
  return useQuery({ queryKey: ['dashboard'], queryFn: () => getDashboard(client) })
}
