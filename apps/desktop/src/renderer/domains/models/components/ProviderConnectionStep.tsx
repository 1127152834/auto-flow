import { FormField } from '../../../shared/components/FormField'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { Textarea } from '../../../shared/components/ui/textarea'
import type { ProviderDraft } from '../model'
import type { ProviderKind, ProviderPreset } from '../provider-catalog'
import { ProviderLogo } from './ProviderLogo'

const kinds = [['openai', 'OpenAI 官方接口'], ['anthropic', 'Anthropic 官方接口'], ['gemini', 'Google Gemini 接口'], ['openai-compatible', 'OpenAI 兼容接口'], ['custom', '自定义接口']]

export function ProviderConnectionStep({ draft, preset, hasStoredKey, error, disabled = false, onChange }: { draft: ProviderDraft; preset: ProviderPreset; hasStoredKey: boolean; error?: string; disabled?: boolean; onChange(patch: Partial<ProviderDraft>): void }) {
  const required = preset.apiKeyPolicy === 'required' || draft.providerKind === 'anthropic' || draft.providerKind === 'gemini'
  return <section className="grid gap-5">
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><strong className="block">操作未完成</strong>{error}</div>}
    <div className="flex items-center gap-3"><ProviderLogo presetId={draft.presetId} name={draft.name || '供应商'} size="large" /><div><strong className="block text-ink">{preset.displayName}</strong><span className="text-sm text-muted">{preset.category}</span></div></div>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="供应商名称" htmlFor="provider-name"><Input disabled={disabled} value={draft.name} onChange={(event) => onChange({ name: event.target.value })} /></FormField>
      <FormField label="接口协议" htmlFor="provider-kind"><Select clearable={false} disabled={disabled} value={draft.providerKind} onValueChange={(value) => onChange({ providerKind: (value ?? 'openai') as ProviderKind })} options={kinds.map(([value, label]) => ({ value, label }))} /></FormField>
    </div>
    <FormField label="服务地址" htmlFor="provider-url" hint="可以替换为私有网关地址。"><Input disabled={disabled} value={draft.baseUrl ?? ''} onChange={(event) => onChange({ baseUrl: event.target.value || null })} placeholder="https://api.example.com/v1" /></FormField>
    <FormField label={`API Key${required ? '' : '（可选）'}`} htmlFor="provider-key" hint={hasStoredKey && !draft.apiKeyTouched ? '已配置，留空保持原凭据' : required ? '凭据只会发送到该供应商。' : '本地或免鉴权服务可以留空。'}><Input disabled={disabled} type="password" autoComplete="off" value={draft.apiKey} onChange={(event) => onChange({ apiKey: event.target.value, apiKeyTouched: true })} placeholder={hasStoredKey ? '已配置，留空保持原凭据' : '粘贴供应商 API Key'} /></FormField>
    <FormField label="说明" htmlFor="provider-description"><Textarea disabled={disabled} rows={3} value={draft.description} onChange={(event) => onChange({ description: event.target.value })} /></FormField>
    <label className="flex items-center justify-between rounded-xl border border-line p-4"><span><strong className="block text-sm text-ink">启用供应商</strong><small className="text-muted">停用后，其模型不会出现在模型选择器。</small></span><Switch disabled={disabled} aria-label="启用供应商" checked={draft.enabled} onCheckedChange={(checked) => onChange({ enabled: checked })} /></label>
  </section>
}
