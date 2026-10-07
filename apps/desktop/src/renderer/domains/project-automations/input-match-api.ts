import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type InputMatchResult = Schema['InputMatchResponse']
export type InputMatchItem = Schema['InputMatchItem']
export type InputMatchFetcher = (plan: Schema['InputPlan'], signal: AbortSignal) => Promise<InputMatchResult>

/** Remediation M5 B4: pre-checks an unsaved input plan against the data tables. */
export function createInputMatchApi(client: StreamingApiClient, projectId: string) {
  return {
    match: (automationId: string, inputPlan: Schema['InputPlan'], signal?: AbortSignal) =>
      client.request<InputMatchResult>(`/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/input-match`, { method: 'POST', body: { inputPlan }, signal }),
  }
}
