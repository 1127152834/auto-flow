import type { ModelProvider, ModelTestResult } from '../model'
import { Button } from '../../../shared/components/ui/button'

export function ModelTestPanel({ provider, modelKey, enabled, pending, actionDisabled, result, error, checkedAt, onTest }: { provider: ModelProvider; modelKey: string; enabled: boolean; pending: boolean; actionDisabled?: boolean; result?: ModelTestResult; error?: string; checkedAt?: string; onTest(): void }) {
  return <aside className="grid content-start gap-5 border-line md:border-r md:pr-6">
    <div><h3 className="font-semibold text-ink">{provider.name}</h3><p className="text-xs text-muted">供应商</p></div>
    <dl className="grid gap-3 text-sm"><div><dt className="text-muted">模型标识</dt><dd className="break-all">{modelKey || '选择或填写模型标识'}</dd></div><div><dt className="text-muted">状态</dt><dd>{enabled ? '已启用' : '已停用'}</dd></div><div><dt className="text-muted">本次测试</dt><dd>{pending ? '正在测试…' : error ? '测试失败' : result ? `测试通过 · ${checkedAt}` : '尚未测试'}</dd></div></dl>
    <Button type="button" disabled={!modelKey.trim() || pending || actionDisabled} onClick={onTest}>测试模型</Button>
    <p className="text-xs text-muted">发送一条简短对话，检查模型是否正常响应。</p>
    {error ? <div role="alert" className="text-sm text-clay"><strong>模型调用失败</strong><p>{error}</p></div> : result ? <div role="status" className="grid gap-1 text-sm"><strong>{result.modelKey} 调用成功</strong><p>{Math.round(result.latencyMs)} ms · {result.outputPreview || '未返回正文'}</p>{result.reasoningPreview ? <details><summary>查看本次返回的思考内容</summary><p>{result.reasoningPreview}</p></details> : null}</div> : null}
  </aside>
}
