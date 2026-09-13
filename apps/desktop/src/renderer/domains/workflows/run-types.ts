import type { components } from '../../shared/api/generated'

export type RunRead = components['schemas']['RunRead']
export type RunSummary = components['schemas']['RunSummary']
export type RunEvent = components['schemas']['RunEvent']
export type RunArtifacts = components['schemas']['RunArtifacts']
export type RunArtifact = components['schemas']['RunArtifact']
export type RunStart = components['schemas']['RunStart']
export type RunList = components['schemas']['RunList']
export type RunEvents = components['schemas']['RunEvents']

export const isRunActive = (run: Pick<RunSummary, 'state'>) => ['starting', 'running', 'pausing', 'paused', 'failed_paused', 'finishing', 'stopping'].includes(run.state)
export const runStateLabel: Record<RunSummary['state'], string> = {
  pausing: '正在等待暂停', paused: '已暂停', failed_paused: '失败现场待检查', starting: '正在启动', running: '运行中', finishing: '正在清理', stopping: '正在停止',
  succeeded: '已完成', failed: '失败', cancelled: '已停止', interrupted: '已中断',
}

export type DebugOptions = components['schemas']['DebugOptions']
export type DebugCommand = components['schemas']['DebugCommand']
export type DebugCommandRead = components['schemas']['DebugCommandRead']
export type DebugVariables = components['schemas']['DebugVariables']

export function parseDebugValues(text: string): NonNullable<DebugOptions['values']> {
  const values = JSON.parse(text, (_key, value) => {
    if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('变量数字必须为有限值')
    return value
  })
  if (!values || typeof values !== 'object' || Array.isArray(values)) throw new Error('变量须为 JSON 对象，键是变量名')
  return values
}
