import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { createAutomationResourcesApi } from '../../project-automations/resources-api'
import { createProjectsApi } from '../../projects/api'
import { projectKeys } from '../../projects/hooks'
import type { ProjectPatch, ProjectView } from '../../projects/types'
import { useResourceSave } from '../use-resource-save'
import { ProxyPolicyFields, validProxy } from './ProxyPolicyFields'

export function ProjectDefaultsPanel({ project, client, workspaceKey, instanceId, readOnly }: {
  project: ProjectView; client: StreamingApiClient; workspaceKey: string; instanceId: string; readOnly: boolean
}) {
  const api = useMemo(() => createProjectsApi(client), [client])
  const resources = useMemo(() => createAutomationResourcesApi(client, project.projectId), [client, project.projectId])
  const cache = useQueryClient()
  const profiles = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-profiles'], queryFn: ({ signal }) => resources.profiles(signal) })
  const proxies = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-proxies'], queryFn: ({ signal }) => resources.proxies(signal) })
  const [baseline, setBaseline] = useState(project)
  const [draft, setDraft] = useState(project.defaultResources)
  const command = useResourceSave<ProjectPatch, ProjectView>({
    storageKey: `autoflow:environment-defaults:${workspaceKey}:${project.projectId}`,
    submit: (body, key, resume) => resume ? api.resumePatch(project.projectId, body, key) : api.patch(project.projectId, body, key),
    onSaved: saved => {
      setBaseline(saved); setDraft(saved.defaultResources)
      cache.setQueryData(projectKeys.detail(workspaceKey, instanceId, project.projectId), saved)
      void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'projects'] })
    },
  })
  const unavailable = Boolean(draft.profileId && !profiles.data?.items.some(item => item.id === draft.profileId))
  const locked = readOnly || command.busy || Boolean(command.pending)
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline.defaultResources)
  return <section aria-label="新建环境默认设置" className="grid gap-4">
    <p className="m-0 text-sm text-muted">仅用于基于模板新建环境。工作流节点可单独指定；已保存的实例保留各自设置。</p>
    <form className="grid max-w-2xl gap-4" onSubmit={event => { event.preventDefault(); if (!readOnly) void command.save({ expectedManagementRevision: baseline.managementRevision, defaultResources: draft }) }}>
      <label className="grid gap-1 text-sm"><span>默认浏览器模板</span><Select aria-label="默认浏览器模板" value={draft.profileId ?? null} placeholder="由工作流节点指定" disabled={locked} loading={profiles.isPending}
        options={(profiles.data?.items ?? []).map(item => ({ value: item.id, label: item.name }))} onValueChange={profileId => setDraft({ ...draft, profileId })} /></label>
      <ProxyPolicyFields sourceDefault value={draft.proxy} options={proxies.data} disabled={locked} onChange={proxy => setDraft({ ...draft, proxy })} />
      {profiles.isError || proxies.isError ? <p role="alert" className="m-0 text-sm text-warning">资源目录读取失败，请刷新后重试。</p> : null}
      {unavailable ? <p role="alert" className="m-0 text-sm text-warning">默认模板不可用，请重新选择。</p> : null}
      {command.error ? <p role="alert" className="m-0 text-sm text-warning">{command.error}</p> : null}
      {command.pending ? <p role="status" className="m-0 text-sm text-muted">上次保存尚待核对，恢复时使用原设置和原命令。</p> : null}
      {readOnly ? <p className="m-0 text-sm text-muted">当前项目不可编辑。</p> : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" disabled={locked || !dirty} onClick={() => { setBaseline(project); setDraft(project.defaultResources) }}>取消修改</Button>
        <Button type="submit" disabled={readOnly || command.busy || (!command.pending && (!dirty || unavailable || !validProxy(draft.proxy, proxies.data)))}>{command.busy ? '保存中…' : command.pending ? '核对保存结果' : '保存默认设置'}</Button>
      </div>
    </form>
  </section>
}
