import { useEffect, useState } from 'react'
import type { RotationSchedule } from '../api'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'

export const rotationModes = {same_city: '同城轮换', same_city_carriers: '同城跨运营商', full_pool: '全池轮换'}
export function RotationScheduleForm({ value, disabled, canSave, onDirtyChange, onSave, onClear }: {
  value: RotationSchedule; disabled: boolean; canSave: boolean
  onDirtyChange: (dirty: boolean) => void; onSave: (value: RotationSchedule) => void; onClear: () => void
}) {
  const [mode, setMode] = useState<NonNullable<RotationSchedule['mode']>>(value.mode ?? 'same_city')
  const [minutes, setMinutes] = useState(value.interval_minutes ?? 10)
  useEffect(() => { setMode(value.mode ?? 'same_city'); setMinutes(value.interval_minutes ?? 10) }, [value.mode, value.interval_minutes, value.enabled])
  const dirty = mode !== (value.mode ?? 'same_city') || minutes !== (value.interval_minutes ?? 10)
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false) }, [dirty, onDirtyChange])
  const intervals = [...new Set([5, 10, 30, 60, minutes])].sort((a,b) => a-b)
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{value.enabled ? `已开启：${value.mode ? rotationModes[value.mode] : '未知模式'}，每 ${value.interval_minutes} 分钟` : '尚未设置自动轮换'}</p>
    <p className="text-xs text-muted">计划由 ProxyPanel 执行，关闭 AutoFlow 后仍会继续。轮换可能使现有连接中断。</p>
    <fieldset disabled={disabled || !canSave} className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-2 text-sm">轮换模式<Select aria-label="轮换模式" value={mode} onChange={e => setMode(e.target.value as typeof mode)}>{Object.entries(rotationModes).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
      <label className="grid gap-2 text-sm">轮换周期<Select aria-label="轮换周期" value={minutes} onChange={e => setMinutes(Number(e.target.value))}>{intervals.map(item => <option key={item} value={item} disabled={![5,10,30,60].includes(item)}>每 {item} 分钟{![5,10,30,60].includes(item) ? '（当前远程值）' : ''}</option>)}</Select></label>
    </fieldset>
    <div className="flex justify-end gap-2">{value.enabled && <Button disabled={disabled} onClick={onClear}>关闭轮换</Button>}<Button variant="primary" disabled={disabled || !canSave || ![5,10,30,60].includes(minutes) || value.enabled && !dirty} onClick={() => onSave({enabled:true, mode, interval_minutes:minutes})}>{value.enabled ? '保存轮换计划' : '开启轮换计划'}</Button></div>
  </div>
}
