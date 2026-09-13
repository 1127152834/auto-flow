import { useEffect, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { parseDebugValues, type DebugOptions } from '../run-types'

export function DebugStart({ disabled, active, selectedId, onStart }: { disabled: boolean; active?: boolean; selectedId: string | null; onStart(options: DebugOptions): void }) {
  const [start, setStart] = useState<'entry' | 'node' | 'until'>('entry')
  const [text, setText] = useState('{}')
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)
  useEffect(() => { if (active) setExpanded(false) }, [active])
  const submit = () => {
    try {
      const values = parseDebugValues(text)
      setError(''); onStart({ start, targetNodeId: start === 'entry' ? null : selectedId, values })
    } catch (e) { setError(e instanceof Error ? e.message : '初值格式无效') }
  }
  return <details open={expanded} onToggle={e => setExpanded(e.currentTarget.open)} className="border-b border-line bg-surface px-5 py-2" aria-label="启动调试"><summary className="cursor-pointer text-xs font-medium text-clay">调试 · 可见临时浏览器</summary><div className="mt-3 flex flex-wrap items-start gap-3"><Select aria-label="调试起跑方式" value={start} onChange={e => setStart(e.target.value as typeof start)}><option value="entry">从头调试</option><option value="node">从所选顶层节点调试</option><option value="until">运行至所选节点</option></Select><label className="text-xs text-muted">本次调试初值（JSON，支持补充前置输出变量）<textarea aria-label="本次调试初值" className="mt-1 block h-20 w-80 rounded border border-line bg-canvas p-2 font-mono" value={text} onChange={e => setText(e.target.value)} /></label><Button disabled={disabled || start !== 'entry' && !selectedId} onClick={submit}>开始调试</Button><p className="text-xs text-muted">暂停不冻结网页。直接起跑时请先手动准备页面；不继承拾取登录态。</p>{error ? <p role="alert" className="text-xs text-red-700">{error}</p> : null}</div></details>
}
