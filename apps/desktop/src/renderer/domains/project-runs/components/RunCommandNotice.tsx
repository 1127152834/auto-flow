import { Button } from '../../../shared/components/ui/button'
import { useBatchCommand } from '../hooks'
import { presentRunFailure } from '../presentation'

export function RunCommandNotice({ command, disabled = false, readOnly = false }: { command: ReturnType<typeof useBatchCommand>; disabled?: boolean; readOnly?: boolean }) {
  const restoredStart = command.restoredCommand?.type === 'start'
  const action = command.restoredCommand?.type
  const label = action ? { start: '启动', stop: '停止', forceStop: '强制停止' }[action] : null
  const invalidRecovery = command.invalidRecovery
  if (!command.recovering && !invalidRecovery && !command.error) return null
  const message = invalidRecovery
    ? command.error
    : command.notAccepted
      ? `原${label ?? '批次操作'}请求尚未接受，可以使用原操作身份重试或继续编辑。`
      : command.error ? presentRunFailure(command.error) : (label ? `批次${label}请求已接受，正在核对${label}结果。` : '批次操作已接受，正在核对结果。')
  return <div role="alert" className="grid gap-2 rounded-control border border-warning/40 bg-surface p-3 text-sm"><span>{message}</span><span className="flex flex-wrap gap-2">{command.recovering && !command.notAccepted ? <Button size="sm" disabled={disabled || command.busy} onClick={() => void command.lookup()}>核对原操作</Button> : null}{command.notAccepted ? <><Button size="sm" disabled={disabled || command.busy || readOnly && restoredStart} onClick={() => void command.retry()}>使用原操作身份重试</Button><Button size="sm" variant="ghost" disabled={disabled || command.busy} onClick={command.discardNotAccepted}>继续编辑</Button></> : null}{invalidRecovery ? <Button size="sm" variant="ghost" disabled={disabled || command.busy} onClick={command.discardInvalidRecovery}>清除损坏的恢复资料</Button> : null}</span></div>
}
