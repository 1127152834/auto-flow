import { Spinner } from '../../../shared/components/ui/spinner'
import { DotsThree, PencilSimple, Pulse } from '@phosphor-icons/react'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { ModelProvider } from '../model'
import { ProviderLogo } from './ProviderLogo'
import { FeedbackCard, type ModelFeedback } from './FeedbackCard'

const protocolLabels: Record<string, string> = { openai: 'OpenAI', anthropic: 'Anthropic', gemini: 'Google Gemini', 'openai-compatible': 'OpenAI 兼容接口', custom: '自定义接口' }

export function ProviderDetail({ provider, feedback, busy, crudBusy, testing, onTest, onEdit, onToggle, onDelete }: {
  provider: ModelProvider; feedback?: ModelFeedback; busy: boolean; crudBusy: boolean; testing: boolean
  onTest(): void; onEdit(): void; onToggle(): void; onDelete(): void
}) {
  const status = !provider.enabled ? '已停用' : provider.connectionStatus === 'connected' ? '连接正常' : provider.connectionStatus === 'failed' ? '连接异常' : '未测试'
  return <section aria-label="供应商详情" className="grid gap-5">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-start gap-4"><ProviderLogo presetId={provider.presetId} name={provider.name} size="large" /><div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3"><h2 className="m-0 break-words text-xl font-semibold">{provider.name}</h2><Badge className={status === '连接正常' ? 'bg-sage-soft text-sage-strong' : status === '连接异常' ? 'bg-danger-soft text-danger' : 'bg-surface-subtle text-muted'}>{status}</Badge></div>
        <p className="mb-1 mt-2 break-words text-sm text-muted">{provider.description || '暂未填写供应商说明'}</p>
        <p className="m-0 text-xs text-muted">最后检查 · {provider.lastCheckedAt ? new Date(provider.lastCheckedAt).toLocaleString('zh-CN', { hour12: false }) : '尚未检查'}</p>
      </div></div>
      <div className="flex gap-2"><Button onClick={onTest} disabled={busy}>{testing ? <Spinner  size={17} /> : <Pulse size={17} />}测试连接</Button><Button onClick={onEdit} disabled={busy}><PencilSimple size={17} />编辑</Button>
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" aria-label="供应商更多操作" className="w-10 p-0"><DotsThree size={23} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem disabled={crudBusy} onSelect={onToggle}>{provider.enabled ? '停用供应商' : '启用供应商'}</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled={crudBusy} className="text-danger" onSelect={onDelete}>删除供应商</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
      </div>
    </div>
    <dl className="m-0 grid grid-cols-[1fr_2fr_1fr] gap-4 rounded-control border border-line bg-surface-subtle px-4 py-4 max-[640px]:grid-cols-1">
      <div className="min-w-0"><dt className="text-xs text-muted">接口协议</dt><dd className="m-0 mt-2 text-sm">{protocolLabels[provider.providerKind] ?? provider.providerKind}</dd></div>
      <div className="min-w-0"><dt className="text-xs text-muted">服务地址</dt><dd className="m-0 mt-2 break-all font-mono text-xs leading-5">{provider.baseUrl}</dd></div>
      <div><dt className="text-xs text-muted">访问凭据</dt><dd className="m-0 mt-2 text-sm">{provider.apiKeyConfigured ? '已配置 API Key' : '未配置 API Key'}</dd></div>
    </dl>
    {feedback && <FeedbackCard feedback={feedback} />}
  </section>
}
