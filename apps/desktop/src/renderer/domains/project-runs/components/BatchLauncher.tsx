import { useEffect, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import type { Automation, AutomationValidation } from '../../project-automations/types'
import { createBatchStartDraft, type BatchStartDraft, type BatchStartRequest } from '../start-schema'
import { useBatchCommand } from '../hooks'
import { BatchStartDialog } from './BatchStartDialog'
import { RunCommandNotice } from './RunCommandNotice'
import { presentRunFailure } from '../presentation'

export type BatchLauncherProps = { open: boolean; onOpenChange(open: boolean): void; savedAutomation: Automation; validation?: AutomationValidation; validationLoading?: boolean; validationError?: string; onRefreshValidation(): void; workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean; onBatchCreated(batchId: string): void; resourceSummary: { label: string; value: string }[] }
const temporaryOverride = (automation: Automation): BatchStartRequest['environmentOverride'] => {
  const policy = automation.environmentPolicy
  const shared = { ...('profileId' in policy ? { profileId: policy.profileId } : {}), ...('proxyOverride' in policy ? { proxyOverride: policy.proxyOverride } : {}), ...('modelProviderId' in policy ? { modelProviderId: policy.modelProviderId } : {}) }
  return { source: 'newFromProfile', ...shared }
}
export function BatchLauncher(props: BatchLauncherProps) {
  const identity = JSON.stringify([props.workspaceKey, props.projectId, props.savedAutomation.automationId])
  const [draft, setDraft] = useState<BatchStartDraft>(() => createBatchStartDraft(props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks ?? 1))
  const previousIdentity = useRef(identity)
  useEffect(() => { if (previousIdentity.current !== identity) { previousIdentity.current = identity; setDraft(createBatchStartDraft(props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks ?? 1)) } }, [identity, props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks])
  const navigated = useRef(new Set<string>())
  const created = (batchId: string, key: string) => { if (navigated.current.has(key)) return; navigated.current.add(key); notify({ title: '批次已创建', tone: 'success', operationId: JSON.stringify([props.workspaceKey, key]) }); props.onBatchCreated(batchId) }
  const command = useBatchCommand({ client: props.client, workspaceKey: props.workspaceKey, instanceId: props.instanceId, projectId: props.projectId, scope: { type: 'start', automationId: props.savedAutomation.automationId }, disabled: props.disabled, readOnly: props.readOnly, onAccepted(operation, key) { const resource = operation.resource as { type?: unknown; projectId?: unknown; batchId?: unknown }; if (operation.kind === 'startBatch' && resource.type === 'batch' && resource.projectId === props.projectId && typeof resource.batchId === 'string') { created(resource.batchId, key); return true } }, onCompleted(batch, key) { if (batch.projectId === props.projectId && batch.automationId === props.savedAutomation.automationId) created(batch.batchId, key) } })
  const runnable = Boolean(props.validation?.runnable) && !props.disabled && !props.readOnly
  const issueText = props.validation?.issues.map(issue => issue.message).filter(Boolean).join('；')
  const checks = [{ label: '运行条件', value: props.validationLoading ? '正在检查' : props.validationError ? '检查失败' : props.readOnly ? '只读项目' : runnable ? '检查完成' : issueText || '需要配置', accepted: runnable, status: runnable ? '可以启动' : '需要处理' }]
  return <BatchStartDialog open={props.open} formSessionKey={identity} automationName={props.savedAutomation.name} expectedAutomationRevision={props.savedAutomation.managementRevision} parameters={props.savedAutomation.parameterSchema} value={draft} onChange={setDraft} onOpenChange={props.onOpenChange} onSubmit={request => command.start(props.savedAutomation.automationId, request)} checks={checks} resources={props.resourceSummary} submitting={command.busy} recovering={command.recovering} errorMessage={command.error ?? (props.validationError ? presentRunFailure(props.validationError) : undefined)} onConfigure={() => props.onOpenChange(false)} temporaryEnvironmentOverride={temporaryOverride(props.savedAutomation)} recoveryActions={<><RunCommandNotice command={command} disabled={props.disabled} readOnly={props.readOnly}/>{props.validationError ? <Button size="sm" disabled={props.disabled || command.busy} onClick={props.onRefreshValidation}>重新检查运行条件</Button> : null}</>}/>
}
