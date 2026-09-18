import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type ProjectStatistics = Schema['ProjectStatistics']
export type StatisticsTaskPage = Schema['TaskPage']
export type StatisticsInterval = 'day' | 'week' | 'month'
export type StatisticsResult = 'succeeded' | 'failed' | 'cancelled' | 'timed_out' | 'interrupted'
export type StatisticsQuery = { from?: string; to?: string; timezone?: string; automationId?: string; tableId?: string; interval?: StatisticsInterval }
export type StatisticsTaskQuery = { result: StatisticsResult; intervalStart?: string; page: number; pageSize: number; sort?: string }

const encoded = encodeURIComponent
const query = (value: Record<string, string | number | undefined>) => new URLSearchParams(Object.entries(value).filter((entry): entry is [string, string | number] => entry[1] !== undefined).map(([key, item]) => [key, String(item)])).toString()

export function createProjectStatisticsApi(client: StreamingApiClient, projectId: string) {
  const root = `/api/v1/projects/${encoded(projectId)}`
  return {
    get: (filter: StatisticsQuery, signal?: AbortSignal) => client.request<ProjectStatistics>(`${root}/statistics?${query(filter)}`, { signal }),
    tasks: (resultSetId: string, filter: StatisticsTaskQuery, signal?: AbortSignal) => client.request<StatisticsTaskPage>(`${root}/statistics/${encoded(resultSetId)}/tasks?${query(filter)}`, { signal }),
  }
}
