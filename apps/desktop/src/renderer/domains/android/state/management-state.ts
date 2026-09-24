export type ManagementStateInput = {
  runtimeState: 'stopped' | 'starting' | 'ready' | 'retained' | 'missing' | 'unknown'
  operation: { action?: string | null; state?: string | null } | null
  stale: boolean
  allowedActions?: readonly string[]
}

const operationLabels: Record<string, string> = {
  create: '正在创建',
  start: '正在启动',
  stop: '正在停止',
  restart: '正在重启',
  delete: '正在删除',
  recover: '正在核实',
}

const runtimeLabels: Record<ManagementStateInput['runtimeState'], string> = {
  stopped: '已停止',
  starting: '启动中',
  ready: '已就绪',
  retained: '数据已保留',
  missing: '资源缺失',
  unknown: '待核实',
}

export function displayManagementState(value: ManagementStateInput): string {
  if (value.operation && ['queued', 'running', 'waiting_capacity'].includes(value.operation.state ?? '') && value.operation.action) {
    return operationLabels[value.operation.action] ?? '操作中'
  }
  return value.stale || value.runtimeState === 'unknown' ? '待核实' : runtimeLabels[value.runtimeState]
}

export function canManage(value: ManagementStateInput, action: string): boolean {
  if (value.allowedActions) return value.allowedActions.includes(action)
  return !value.stale && value.runtimeState !== 'unknown'
}
