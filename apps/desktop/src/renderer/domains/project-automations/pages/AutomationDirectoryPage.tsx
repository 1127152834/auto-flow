import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { createAutomationApi } from '../api'
import { AutomationDeleteDialog, type AutomationDeleteSubmit } from '../components/AutomationDeleteDialog'
import { AutomationDirectory } from '../components/AutomationDirectory'
import type { Automation, AutomationDirectoryQuery } from '../types'
import { safeProjectError } from '../../projects/presentation-error'

const defaults: AutomationDirectoryQuery = { query: '', sort: '-updatedAt', page: 1, pageSize: 50 }
function readQuery(key: string): AutomationDirectoryQuery {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? '{}') as Partial<AutomationDirectoryQuery>
    return { query: typeof value.query === 'string' ? value.query : '', sort: ['name', '-name', 'updatedAt', '-updatedAt'].includes(value.sort ?? '') ? value.sort! : defaults.sort, page: Number.isSafeInteger(value.page) && value.page! > 0 && value.page! <= 2147483647 ? value.page! : 1, pageSize: 50 }
  } catch { return defaults }
}
export type AutomationDirectoryPageProps = {
  workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean
  onOpen(automationId: string): void; onCreate(): void; onOpenStudio?(): void
}
export function AutomationDirectoryPage(props: AutomationDirectoryPageProps) {
  return <Directory key={JSON.stringify([props.workspaceKey, props.projectId])} {...props} />
}
function Directory({ workspaceKey, instanceId, projectId, client, disabled, readOnly, onOpen, onCreate, onOpenStudio }: AutomationDirectoryPageProps) {
  const key = `autoflow:automations-ui:${JSON.stringify([workspaceKey, projectId])}`
  const [query, setQuery] = useState(() => readQuery(key))
  const [removing, setRemoving] = useState<{ automation: Automation; key: string } | null>(null)
  const api = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const cache = useQueryClient()
  const result = useQuery({ queryKey: [workspaceKey, instanceId, 'automations', projectId, query], queryFn: ({ signal }) => api.list(query, signal), enabled: !disabled })
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(query)) } catch { /* Storage can be unavailable. */ } }, [key, query])
  useEffect(() => {
    if (!result.data) return
    const last = Math.max(1, Math.ceil(result.data.total / query.pageSize))
    if (query.page > last) setQuery(current => ({ ...current, page: last }))
  }, [result.data, query.page, query.pageSize])
  const submit = (values: AutomationDeleteSubmit) => {
    // The key stays with this confirmation session so an uncertain outcome is
    // replayed under its original identity instead of deleting something else.
    if (!removing) throw new Error('缺少待删除的自动化')
    return api.remove(removing.automation.automationId, values, removing.key)
  }
  return <>
    <AutomationDirectory items={result.data?.items ?? []} total={result.data?.total ?? 0} page={query.page} pageSize={query.pageSize} query={query.query} sort={query.sort} loading={result.isLoading} refreshing={result.isFetching || disabled} readOnly={readOnly} errorMessage={result.error ? safeProjectError(result.error) : undefined}
      onQueryChange={value => setQuery(current => ({ ...current, query: value, page: 1 }))} onSortChange={sort => setQuery(current => ({ ...current, sort, page: 1 }))} onPageChange={page => setQuery(current => ({ ...current, page }))}
      onOpen={automation => onOpen(automation.automationId)} onEdit={automation => onOpen(automation.automationId)} onDelete={readOnly ? undefined : automation => setRemoving({ automation, key: crypto.randomUUID() })} onCreate={onCreate} onOpenStudio={onOpenStudio} onRetry={() => void result.refetch()} />
    <AutomationDeleteDialog open={Boolean(removing)} automation={removing?.automation ?? null} disabled={disabled} onOpenChange={open => { if (!open) setRemoving(null) }} onLoadImpact={() => {
      if (!removing) return Promise.reject(new Error('缺少待删除的自动化'))
      return api.impact(removing.automation.automationId)
    }} onSubmit={submit} onFinished={operation => {
      void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'automations', projectId] })
      notify({ title: operation.status === 'succeeded' ? '自动化已删除' : '删除命令已接受，正在处理', tone: 'success', operationId: operation.operationId })
    }} />
  </>
}
