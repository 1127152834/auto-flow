import { safeProjectError } from '../../projects/presentation-error'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import type { Automation, AutomationValidation } from '../../project-automations/types'
import { createBatchStartDraft, type BatchStartDraft, type BatchStartRequest } from '../start-schema'
import { useBatchCommand } from '../hooks'
import { BatchStartDialog } from './BatchStartDialog'
import { RunCommandNotice } from './RunCommandNotice'
import { presentRunFailure } from '../presentation'
import { createProjectRunsApi } from '../api'
import { DataInputPreview, type DataInputPreviewOutcome } from './DataInputPreview'

export type BatchLauncherProps = { open: boolean; onOpenChange(open: boolean): void; savedAutomation: Automation; validation?: AutomationValidation; validationLoading?: boolean; validationError?: string; onRefreshValidation(): void; workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean; onBatchCreated(batchId: string): void; resourceSummary: { label: string; value: string }[] }
const temporaryOverride = (automation: Automation): BatchStartRequest['environmentOverride'] => {
  const policy = automation.environmentPolicy
  const shared = { ...('profileId' in policy ? { profileId: policy.profileId } : {}), ...('proxyOverride' in policy ? { proxyOverride: policy.proxyOverride } : {}), ...('modelProviderId' in policy ? { modelProviderId: policy.modelProviderId } : {}) }
  return { source: 'newFromProfile', ...shared }
}
export function BatchLauncher(props: BatchLauncherProps) {
  const identity = JSON.stringify([props.workspaceKey, props.projectId, props.savedAutomation.automationId])
  const hasInputs = props.savedAutomation.inputPlan.inputs.length > 0
  const [draft, setDraft] = useState<BatchStartDraft>(() => ({ ...createBatchStartDraft(props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks ?? 1), concurrency: hasInputs ? String(props.savedAutomation.runPolicy.concurrency) : '1' }))
  const previousIdentity = useRef(identity)
  useEffect(() => { if (previousIdentity.current !== identity) { previousIdentity.current = identity; setDraft({ ...createBatchStartDraft(props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks ?? 1), concurrency: hasInputs ? String(props.savedAutomation.runPolicy.concurrency) : '1' }) } }, [hasInputs, identity, props.savedAutomation.parameterSchema, props.savedAutomation.runPolicy.maxTasks, props.savedAutomation.runPolicy.concurrency])
  const navigated = useRef(new Set<string>())
  const created = (batchId: string, key: string) => { if (navigated.current.has(key)) return; navigated.current.add(key); notify({ title: '批次已创建', tone: 'success', operationId: JSON.stringify([props.workspaceKey, key]) }); props.onBatchCreated(batchId) }
  const command = useBatchCommand({ client: props.client, workspaceKey: props.workspaceKey, instanceId: props.instanceId, projectId: props.projectId, scope: { type: 'start', automationId: props.savedAutomation.automationId }, disabled: props.disabled, readOnly: props.readOnly, onAccepted(operation, key) { const resource = operation.resource as { type?: unknown; projectId?: unknown; batchId?: unknown }; if (operation.kind === 'startBatch' && resource.type === 'batch' && resource.projectId === props.projectId && typeof resource.batchId === 'string') { created(resource.batchId, key); return true } }, onCompleted(batch, key) { if (batch.projectId === props.projectId && batch.automationId === props.savedAutomation.automationId) created(batch.batchId, key) } })
  const api = useMemo(() => createProjectRunsApi(props.client, props.projectId), [props.client, props.projectId])
  const [preview, setPreview] = useState<{ data?: Awaited<ReturnType<typeof api.previewInputs>>; loading: boolean; error?: unknown }>({ loading: false })
  useEffect(() => {
    if (!props.open || !hasInputs || props.disabled) { setPreview({ loading: false }); return }
    const controller = new AbortController()
    setPreview({ loading: true })
    void api.previewInputs(props.savedAutomation.automationId, props.savedAutomation.managementRevision, controller.signal)
      .then(data => { if (!controller.signal.aborted) setPreview({ data, loading: false }) })
      .catch(error => { if (!controller.signal.aborted) setPreview({ loading: false, error }) })
    return () => controller.abort()
  }, [api, hasInputs, props.disabled, props.instanceId, props.open, props.savedAutomation.automationId, props.savedAutomation.managementRevision, props.workspaceKey])
  const inputsReady = !hasInputs || preview.data?.runnable === true
  const selectionStatus = preview.data?.selectionStatus
  const inputsAccepted = inputsReady || selectionStatus === 'temporarilyBusy' || selectionStatus === 'noMatch'
  const inputCheckText = selectionStatus === 'temporarilyBusy' ? '数据暂被占用，批次将等待释放' : selectionStatus === 'noMatch' ? '当前没有匹配数据，启动后重新核验' : inputsReady ? '已找到完整输入组' : '当前不能领取完整输入组'
  const issueText = props.validation?.issues.map(safeProjectError).join('；')
  const checks = [{ label: '运行条件', value: props.validationLoading ? '正在检查' : props.validationError ? '检查失败' : props.readOnly ? '只读项目' : Boolean(props.validation?.runnable) ? '检查完成' : issueText || '需要配置', accepted: Boolean(props.validation?.runnable), status: props.validation?.runnable ? '可以启动' : '需要处理' }, ...(hasInputs ? [{ label: '项目数据', value: preview.loading ? '正在预检数据输入' : preview.error ? '预检失败' : inputCheckText, accepted: inputsAccepted, status: inputsAccepted ? '可以启动' : '需要处理' }] : [])]
  const inputPreview = hasInputs ? <DataInputPreview loading={preview.loading} error={preview.error ? presentRunFailure(preview.error, '服务连接已中断，请重新预检') : undefined} inputs={(preview.data?.inputs ?? []).map(item => ({ alias: item.alias, tableDisplay: item.tableDisplay, recordDisplay: item.recordDisplay, values: (item.values ?? []).map(value => ({ label: typeof value.fieldName === 'string' ? value.fieldName : '字段', value: String(value.value ?? 'null') })), outcome: item.outcome as DataInputPreviewOutcome, required: item.required, scannedCount: item.scannedCount ?? undefined, detail: item.detail ?? undefined }))}/> : undefined
  return <BatchStartDialog dataBatch={hasInputs} allowUnlimited={props.savedAutomation.inputPlan.inputs.some(input => input.required === true)} continueAfterFailure={props.savedAutomation.runPolicy.continueAfterFailure} open={props.open} formSessionKey={identity} automationName={props.savedAutomation.name} expectedAutomationRevision={props.savedAutomation.managementRevision} parameters={props.savedAutomation.parameterSchema} value={draft} onChange={setDraft} onOpenChange={props.onOpenChange} onSubmit={request => command.start(props.savedAutomation.automationId, request)} checks={checks} resources={props.resourceSummary} submitting={command.busy} recovering={command.recovering} errorMessage={command.error ?? (preview.error ? presentRunFailure(preview.error, '数据输入预检失败') : props.validationError ? presentRunFailure(props.validationError) : undefined)} onConfigure={() => props.onOpenChange(false)} inputPreview={inputPreview} temporaryEnvironmentOverride={temporaryOverride(props.savedAutomation)} recoveryActions={<><RunCommandNotice command={command} disabled={props.disabled} readOnly={props.readOnly}/>{props.validationError ? <Button size="sm" disabled={props.disabled || command.busy} onClick={props.onRefreshValidation}>重新检查运行条件</Button> : null}</>}/>
}
