import type { AndroidDevice } from './api'
export const groups = ['可分配', '使用中', '启停与待处理'] as const
export function deviceGroup(device: AndroidDevice): typeof groups[number] {
  if (device.control === 'recovery_required' || device.control === 'managing') return groups[2]
  if (device.ownerRunId || device.control !== 'idle') return groups[1]
  return device.androidStatus === 'ready' ? groups[0] : groups[2]
}
export function deviceStatus(device: AndroidDevice): string {
  if (device.control === 'managing') return device.operation?.stage ?? '操作中'
  if (device.control === 'recovery_required') return '需要处理'
  if (['manual', 'opening_manual', 'closing_manual'].includes(device.control)) return '手动控制中'
  if (device.ownerRunId) return '工作流占用'
  return ({ ready: '已就绪', stopped: '已停止', starting: '启动中', retained: '数据已保留', missing: '资源缺失' } as Record<string, string>)[device.androidStatus] ?? '状态待核实'
}
export const canOpen = (device: AndroidDevice) => device.control === 'idle' && ['ready', 'stopped'].includes(device.androidStatus)
