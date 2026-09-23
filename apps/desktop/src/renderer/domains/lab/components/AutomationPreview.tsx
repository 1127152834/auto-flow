import { useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { automationPreview } from '../preview'
import type { LayaResult } from '../types'

export function AutomationPreview({ result }: { result: LayaResult | null }) {
  const [threshold, setThreshold] = useState(0.85)
  const [copyMessage, setCopyMessage] = useState('')
  if (!result) return null
  const preview = automationPreview(result, threshold)
  return <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-labelledby="lab-preview-heading">
    <div><h2 id="lab-preview-heading" className="m-0 text-lg font-semibold">自动化预览</h2><p className="mb-0 mt-1 text-sm text-muted">只展示模拟动作。阈值未经业务校准，不会触发真实流程。</p></div>
    <label className="grid gap-2 text-sm font-medium" htmlFor="lab-threshold">演示置信度阈值：{Math.round(threshold * 100)}%<input id="lab-threshold" type="range" min="0.5" max="0.99" step="0.01" value={threshold} onChange={event => setThreshold(Number(event.target.value))} className="w-full accent-clay" /></label>
    <div className="grid gap-2">{preview.suggestedActions.map(action => <div key={action.questionId} className="flex flex-wrap items-center justify-between gap-2 rounded-control bg-surface-subtle px-3 py-2 text-sm"><span>{action.questionId}</span><strong>{action.kind === 'human_review' ? '转人工复核' : action.kind === 'route' ? `建议分流：${action.target}` : action.kind === 'set_score' && typeof action.value === 'number' ? `记录评分：${action.value.toFixed(2)}` : action.kind === 'flag' ? '建议标记' : '继续流程'}</strong></div>)}</div>
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="m-0 text-sm font-semibold">结构化节点输入预览</h3><Button size="sm" onClick={() => { if (!navigator.clipboard?.writeText) { setCopyMessage('复制不可用，请手动选择文本'); return } void navigator.clipboard.writeText(JSON.stringify(preview, null, 2)).then(() => setCopyMessage('已复制 JSON')).catch(() => setCopyMessage('复制失败，请手动选择文本')) }}>复制 JSON</Button></div>
    <pre className="m-0 max-h-72 overflow-auto rounded-control bg-ink p-4 text-xs leading-relaxed text-white">{JSON.stringify(preview, null, 2)}</pre><span role="status" className="text-xs text-muted">{copyMessage}</span>
  </section>
}
