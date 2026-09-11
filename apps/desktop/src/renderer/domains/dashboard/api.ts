import type { ApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

export type DashboardSnapshot = components['schemas']['DashboardRead']
export const getDashboard = (client: ApiClient) => client.request<DashboardSnapshot>('/api/v1/dashboard')
