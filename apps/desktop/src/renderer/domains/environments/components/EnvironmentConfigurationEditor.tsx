import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { createKernelsApi } from '../../kernels/api'
import { createAutomationResourcesApi } from '../../project-automations/resources-api'
import { createEnvironmentApi, type Environment, type EnvironmentPatch } from '../api'
import { useResourceSave } from '../use-resource-save'
import { ProxyPolicyFields, validProxy } from './ProxyPolicyFields'

export function EnvironmentConfigurationEditor({ environment, client, workspaceKey, instanceId, disabled, onSaved }: {
  environment: Environment; client: StreamingApiClient; workspaceKey: string; instanceId: string; disabled: boolean; onSaved(): void
}) {
  const { projectId, environmentId } = environment.ref
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const catalog = useMemo(() => createAutomationResourcesApi(client, projectId), [client, projectId])
  const kernelsApi = useMemo(() => createKernelsApi(client), [client])
  const proxies = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-proxies'], queryFn: ({ signal }) => catalog.proxies(signal) })
  const kernels = useQuery({ queryKey: [workspaceKey, instanceId, 'installed-kernels'], queryFn: () => kernelsApi.installed() })
  const [revision] = useState(environment.ref)
  const [draft, setDraft] = useState(environment.browserConfiguration!)
  const command = useResourceSave<EnvironmentPatch, Environment>({
    storageKey: `autoflow:environment-configuration:${workspaceKey}:${projectId}:${environmentId}`,
    submit: (body, key, resume) => api.patchConfiguration(environmentId, body, key, resume), onSaved,
  })
  const installed = kernels.data?.items.some(item => item.edition === draft.kernel.edition && item.version === draft.kernel.version)
  const locked = disabled || command.busy || Boolean(command.pending)
  return <form aria-label="实例浏览器设置" className="grid gap-4" onSubmit={event => { event.preventDefault(); if (!disabled) void command.save({ expectedMetadataRevision: revision.metadataRevision, expectedContentGeneration: revision.contentGeneration, browserConfiguration: draft }) }}>
    <ProxyPolicyFields value={draft.proxy} options={proxies.data} disabled={locked} onChange={proxy => { if (proxy.mode !== 'sourceDefault') setDraft({ ...draft, proxy }) }} />
    <p className="m-0 text-sm">浏览器内核：{draft.kernel.edition === 'public' ? '公开版' : '授权版'} {draft.kernel.version}</p>
    <p className="m-0 text-sm text-muted">已有登录态的跨内核迁移尚未验证。使用其他内核时，请新建环境。</p>
    {!installed && !kernels.isPending ? <p role="alert" className="m-0 text-sm text-warning">原内核未安装或无法读取，请先在浏览器配置中安装。</p> : null}
    {proxies.isError ? <p role="alert">代理目录读取失败。</p> : null}
    {command.error ? <p role="alert" className="m-0 text-sm text-warning">{command.error}</p> : null}
    {command.pending ? <p role="status" className="m-0 text-sm text-muted">有一条保存命令尚待核对，继续使用原配置和原命令恢复。</p> : null}
    <div className="flex justify-end"><Button type="submit" disabled={disabled || command.busy || (!command.pending && (!installed || !validProxy(draft.proxy, proxies.data)))}>{command.busy ? '保存中…' : command.pending ? '核对并恢复保存' : '保存实例设置'}</Button></div>
  </form>
}
