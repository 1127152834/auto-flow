import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { createAutomationApi } from '../api'
import { AutomationDirectory } from '../components/AutomationDirectory'
import type { AutomationDirectoryQuery } from '../types'

const defaults: AutomationDirectoryQuery = { query: '', sort: '-updatedAt', page: 1, pageSize: 50 }
function readQuery(key: string): AutomationDirectoryQuery {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? '{}') as Partial<AutomationDirectoryQuery>
    return { query: typeof value.query === 'string' ? value.query : '', sort: ['name', '-name', 'updatedAt', '-updatedAt'].includes(value.sort ?? '') ? value.sort! : defaults.sort, page: Number.isSafeInteger(value.page) && value.page! > 0 && value.page! <= 2147483647 ? value.page! : 1, pageSize: 50 }
  } catch { return defaults }
}
export type AutomationDirectoryPageProps = {
  workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean
  onOpen(automationId: string): void; onCreate(): void
}
export function AutomationDirectoryPage(props: AutomationDirectoryPageProps) {
  return <Directory key={JSON.stringify([props.workspaceKey, props.projectId])} {...props} />
}
function Directory({ workspaceKey, instanceId, projectId, client, disabled, readOnly, onOpen, onCreate }: AutomationDirectoryPageProps) {
  const key = `autoflow:automations-ui:${JSON.stringify([workspaceKey, projectId])}`
  const [query, setQuery] = useState(() => readQuery(key))
  const api = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const result = useQuery({ queryKey: [workspaceKey, instanceId, 'automations', projectId, query], queryFn: ({ signal }) => api.list(query, signal), enabled: !disabled })
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(query)) } catch { /* Storage can be unavailable. */ } }, [key, query])
  useEffect(() => {
    if (!result.data) return
    const last = Math.max(1, Math.ceil(result.data.total / query.pageSize))
    if (query.page > last) setQuery(current => ({ ...current, page: last }))
  }, [result.data, query.page, query.pageSize])
  return <AutomationDirectory items={result.data?.items ?? []} total={result.data?.total ?? 0} page={query.page} pageSize={query.pageSize} query={query.query} sort={query.sort} loading={result.isLoading} refreshing={result.isFetching || disabled} readOnly={readOnly} errorMessage={result.error?.message}
    onQueryChange={value => setQuery(current => ({ ...current, query: value, page: 1 }))} onSortChange={sort => setQuery(current => ({ ...current, sort, page: 1 }))} onPageChange={page => setQuery(current => ({ ...current, page }))}
    onOpen={automation => onOpen(automation.automationId)} onEdit={automation => onOpen(automation.automationId)} onCreate={onCreate} onRetry={() => void result.refetch()} />
}
