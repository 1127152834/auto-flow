import { useState } from 'react'
import { Select } from '../components/ui/select-radix'
import { Autocomplete, Combobox } from '../components/ui/combobox'
import type { ChoiceOption } from '../components/ui/choice-types'
const options: ChoiceOption[] = [{ value: '', label: '跟随系统' }, { value: 'stable', label: 'Stable', description: '公开版稳定通道', keywords: ['稳定'] }, { value: 'preview', label: 'Preview', description: '正式版预览通道' }, { value: 'disabled', label: '不可选择', disabled: true }, { value: 'v:x', label: '同名资源', description: '标识 v:x' }, { value: '__custom__', label: '同名资源', description: '标识 __custom__' }, { value: 'long', label: '长名称 · ' + '中文 English 资源说明 '.repeat(15) }]
export function ChoiceCases({ size }: { size: 'sm' | 'md' }) {
  const [value, setValue] = useState<string | null>(null), [free, setFree] = useState(''), [selected, setSelected] = useState(''), [failed, setFailed] = useState(true)
  return <section aria-labelledby="choices-title" className="grid gap-5 rounded-card border border-line bg-surface p-6"><div><h2 id="choices-title" className="font-semibold">选择与自由输入</h2><p className="mt-1 text-xs text-muted">A04 · null 与空串、重复标签、长文、失效值和重试</p></div>
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="grid gap-2 text-sm"><span>通道选择</span><Select aria-label="通道选择" size={size} options={options} value={value} onValueChange={setValue} /></div>
      <div className="grid gap-2 text-sm"><span>搜索通道</span><Combobox aria-label="搜索通道" size={size} options={options} value={value} onValueChange={setValue} /></div>
      <div className="grid gap-2 text-sm"><span>自由输入样本</span><Autocomplete aria-label="自由输入样本" size={size} options={options} value={free} onValueChange={setFree} onOptionSelect={option => setSelected(option.value)} /></div>
      <div className="grid gap-2 text-sm"><span>加载失败</span><Combobox aria-label="失败目录" size={size} options={options} value={null} onValueChange={setValue} errorMessage={failed ? '发布列表加载失败，已安装选项仍可用' : undefined} onRetry={() => setFailed(false)} /></div>
      <div className="grid gap-2 text-sm"><span>失效只读值</span><Select aria-label="只读通道" options={options} value="removed:kernel" onValueChange={setValue} readOnly size={size} /></div>
      <div className="grid gap-2 text-sm"><span>禁用选择</span><Select aria-label="禁用通道" options={options} value="stable" onValueChange={setValue} disabled size={size} /></div>
      <div className="grid gap-2 text-sm"><span>选项加载中</span><Combobox aria-label="加载目录" options={[]} value={null} onValueChange={setValue} loading size={size} /></div>
      <div className="grid gap-2 text-sm"><span>空目录</span><Combobox aria-label="空目录" options={[]} value={null} onValueChange={setValue} size={size} /></div>
    </div><p role="status" className="text-xs text-muted">选择值：{JSON.stringify(value)}；自由文本：{JSON.stringify(free)}；最近选项回调：{selected || '无'}</p>
  </section>
}
