import type { components } from '../../shared/api/generated'

export type RunRead = components['schemas']['RunRead']
export type RunSummary = components['schemas']['RunSummary']
export type RunEvent = components['schemas']['RunEvent']
export type RunArtifact = components['schemas']['RunArtifact']
export type RunStart = components['schemas']['RunStart']
export type RunList = components['schemas']['RunList']
export type RunEvents = components['schemas']['RunEvents']

export const isRunActive = (run: Pick<RunSummary, 'state'>) => ['starting', 'running', 'finishing', 'stopping', 'waiting_manual', 'resuming'].includes(run.state)
export const runStateLabel: Record<RunSummary['state'], string> = {
  waiting_manual: '等待人工', resuming: '正在收回控制权', starting: '正在启动', running: '运行中', finishing: '正在清理', stopping: '正在停止',
  succeeded: '已完成', failed: '失败', cancelled: '已停止', interrupted: '已中断',
}
