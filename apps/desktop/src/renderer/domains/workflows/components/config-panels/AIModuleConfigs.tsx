// Source: WebRPA@5ccb900e, components/workflow/config-panels/AIModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import type React from 'react'
import { useEffect, useState } from 'react'
import type { NodeData } from '../../editor-store'
import type { ModelOptionList } from '../../api'
import { modelApi } from '../../api'
import { Label } from '../controls/label'
import { Checkbox } from '../controls/checkbox'
import { NumberInput } from '../controls/number-input'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { ImagePathInput } from '../controls/image-path-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { VariableRefInput } from '../controls/variable-ref-input'
import { Bot, Cpu } from 'lucide-react'
import { useGlobalConfigStore } from '../../hooks/stores/globalConfigStore'

type RenderSelectorInput = (id: string, label: string, placeholder: string) => React.ReactNode
type ModelOption = ModelOptionList['items'][number]
type BatchChange = (data: Partial<NodeData>) => void

// 模型凭据只留在主应用；工作流文档仅保存稳定 modelId。
export function AIModelPicker({ data, onBatchChange }: { data: NodeData; onBatchChange: BatchChange }) {
  const [models, setModels] = useState<ModelOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const autoFallback = useGlobalConfigStore((s) => s.config.ai?.autoFallback) ?? false

  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true)
      const result = await modelApi.listOptions()
      if (!active) return
      if (!result.success || !Array.isArray(result.data?.items)) {
        setError(`模型列表加载失败：${result.error || '响应格式错误'}`)
        setModels([])
      } else {
        setError('')
        setModels(result.data.items)
      }
      setLoading(false)
    }
    void load()
    window.addEventListener('studio:transport-changed', load)
    return () => { active = false; window.removeEventListener('studio:transport-changed', load) }
  }, [])

  useEffect(() => {
    if (loading || !data.modelId) return
    const desired = autoFallback ? models.filter(model => model.id !== data.modelId).map(model => model.id) : []
    const current = Array.isArray(data.fallbackModelIds) ? data.fallbackModelIds : []
    if (JSON.stringify(current) !== JSON.stringify(desired)) {
      onBatchChange({ fallbackModelIds: desired.length ? desired : undefined })
    }
  }, [autoFallback, data.modelId, loading, models, onBatchChange])

  const selectedMissing = Boolean(data.modelId) && !loading && !error && !models.some(model => model.id === data.modelId)
  return (
    <div className="space-y-2">
      <Label className="flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5 text-violet-600" />主应用模型</Label>
      <Select
        value={(data.modelId as string) || ''}
        disabled={loading || models.length === 0}
        onChange={(e) => {
          const modelId = e.target.value || undefined
          onBatchChange({
            modelId,
            apiUrl: undefined,
            apiKey: undefined,
            apiBase: undefined,
            engineId: undefined,
            model: undefined,
            llmProvider: undefined,
            llmModel: undefined,
            azureEndpoint: undefined,
            fallbackModels: undefined,
          })
        }}
      >
        <option value="">{loading ? '正在读取主应用模型…' : '请选择模型…'}</option>
        {models.map((model) => (
          <option key={model.id} value={model.id}>{model.displayName}（{model.providerName}）</option>
        ))}
      </Select>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {!loading && !error && models.length === 0 && <p className="text-xs text-amber-700">主应用尚未配置可用模型</p>}
      {selectedMissing && <p className="text-xs text-amber-700">已选模型不可用，请从主应用模型中重新选择</p>}
      <p className="text-xs text-muted-foreground">模型地址和密钥由主应用安全管理，不写入工作流文档。</p>
    </div>
  )
}

// AI大脑配置
export function AIChatConfig({ data, onChange, onBatchChange }: { data: NodeData; onChange: (key: string, value: unknown) => void; onBatchChange: BatchChange }) {
  return (
    <>
      <AIModelPicker data={data} onBatchChange={onBatchChange} />
      <div className="space-y-2">
        <Label htmlFor="systemPrompt">系统提示词 (可选)</Label>
        <VariableInput
          value={(data.systemPrompt as string) || ''}
          onChange={(v) => onChange('systemPrompt', v)}
          placeholder="设定AI的角色和行为，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="userPrompt">用户提示词</Label>
        <VariableInput
          value={(data.userPrompt as string) || ''}
          onChange={(v) => onChange('userPrompt', v)}
          placeholder="发送给AI的内容，支持 {变量名}"
          multiline
          rows={4}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储回复到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="temperature">温度 (0-2)</Label>
        <NumberInput
          id="temperature"
          value={(data.temperature as number) ?? 0.7}
          onChange={(v) => onChange('temperature', v)}
          defaultValue={0.7}
          min={0}
          max={2}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="maxTokens">最大Token数</Label>
        <NumberInput
          id="maxTokens"
          value={(data.maxTokens as number) ?? 2000}
          onChange={(v) => onChange('maxTokens', v)}
          defaultValue={2000}
          min={1}
        />
      </div>
    </>
  )
}

// AI视觉配置
export function AIVisionConfig({ 
  data, 
  onChange, 
  onBatchChange,
  renderSelectorInput 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
  onBatchChange: BatchChange
  renderSelectorInput: RenderSelectorInput
}) {
  const imageSource = (data.imageSource as string) || 'element'
  
  return (
    <>
      <AIModelPicker data={data} onBatchChange={onBatchChange} />
      
      <div className="space-y-2">
        <Label htmlFor="imageSource">图片来源</Label>
        <Select
          id="imageSource"
          value={imageSource}
          onChange={(e) => onChange('imageSource', e.target.value)}
        >
          <option value="element">页面元素截图</option>
          <option value="screenshot">当前页面截图</option>
          <option value="url">图片URL</option>
          <option value="variable">变量 (Base64/路径)</option>
        </Select>
      </div>
      
      {imageSource === 'element' && (
        renderSelectorInput('imageSelector', '图片元素选择器', 'img.target 或 #image')
      )}
      
      {imageSource === 'url' && (
        <div className="space-y-2">
          <Label htmlFor="imageUrl">图片地址（网址或本地路径）</Label>
          <ImagePathInput
            value={(data.imageUrl as string) || ''}
            onChange={(v) => onChange('imageUrl', v)}
            placeholder="https://example.com/image.jpg 或本地图片路径，支持 {变量名}"
          />
        </div>
      )}
      
      {imageSource === 'variable' && (
        <div className="space-y-2">
          <Label htmlFor="imageVariable">图片变量名</Label>
          <VariableRefInput
            id="imageVariable"
            value={(data.imageVariable as string) || ''}
            onChange={(v) => onChange('imageVariable', v)}
            placeholder="填写变量名，如: imageData"
          />
          <p className="text-xs text-muted-foreground">
            直接填写包含Base64或文件路径的变量名
          </p>
        </div>
      )}
      
      <div className="space-y-2">
        <Label htmlFor="userPrompt">提问内容</Label>
        <VariableInput
          value={(data.userPrompt as string) || ''}
          onChange={(v) => onChange('userPrompt', v)}
          placeholder="请描述这张图片中的内容，支持 {变量名}"
          multiline
          rows={4}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="variableName">存储回复到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="maxTokens">最大Token数</Label>
        <NumberInput
          id="maxTokens"
          value={(data.maxTokens as number) ?? 1000}
          onChange={(v) => onChange('maxTokens', v)}
          defaultValue={1000}
          min={1}
        />
      </div>
      
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800">
          <strong>AI视觉模块</strong>可以让AI"看"图片并回答问题。<br/>
          • 支持识别图片内容、提取文字、分析图表等<br/>
          • 推荐使用智谱GLM-4V或OpenAI GPT-4V模型
        </p>
      </div>
    </>
  )
}

// API请求配置
export function ApiRequestConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const method = (data.requestMethod as string) || 'GET'
  const hasBody = ['POST', 'PUT', 'PATCH'].includes(method)

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="requestUrl">请求地址</Label>
        <VariableInput
          value={(data.requestUrl as string) || ''}
          onChange={(v) => onChange('requestUrl', v)}
          placeholder="https://api.example.com/data，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="requestMethod">请求方法</Label>
        <Select
          id="requestMethod"
          value={method}
          onChange={(e) => onChange('requestMethod', e.target.value)}
        >
          <option value="GET">GET</option>
          <option value="POST">POST</option>
          <option value="PUT">PUT</option>
          <option value="DELETE">DELETE</option>
          <option value="PATCH">PATCH</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="requestHeaders">请求头（JSON 格式，可选）</Label>
        <textarea
          id="requestHeaders"
          className="w-full min-h-[60px] px-3 py-2 text-sm rounded-md border border-input bg-background font-mono text-xs"
          value={(data.requestHeaders as string) || ''}
          onChange={(e) => onChange('requestHeaders', e.target.value)}
          placeholder='{"Content-Type": "application/json", "Authorization": "Bearer {token}"}'
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="requestCookies">Cookies（可选）</Label>
        <textarea
          id="requestCookies"
          className="w-full min-h-[60px] px-3 py-2 text-sm rounded-md border border-input bg-background font-mono text-xs"
          value={(data.requestCookies as string) || ''}
          onChange={(e) => onChange('requestCookies', e.target.value)}
          placeholder={'JSON格式：{"session": "abc123"}\n或键值对：session=abc123; token=xyz'}
        />
        <p className="text-xs text-muted-foreground">
          支持 JSON 格式或 <code>key=value; key2=value2</code> 格式，支持变量引用
        </p>
      </div>
      {hasBody && (
        <div className="space-y-2">
          <Label htmlFor="requestBody">请求体（可选）</Label>
          <textarea
            id="requestBody"
            className="w-full min-h-[80px] px-3 py-2 text-sm rounded-md border border-input bg-background font-mono text-xs"
            value={(data.requestBody as string) || ''}
            onChange={(e) => onChange('requestBody', e.target.value)}
            placeholder='{"key": "value", "name": "{变量名}"}'
          />
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="variableName">存储响应到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名（存储完整响应 JSON）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="requestTimeout">超时时间（秒）</Label>
        <NumberInput
          id="requestTimeout"
          value={(data.requestTimeout as number) ?? 30}
          onChange={(v) => onChange('requestTimeout', v)}
          defaultValue={30}
          min={1}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        发送 HTTP 请求并将响应存储到变量，可配合 JSON 解析模块提取数据
      </p>
    </>
  )
}

// AI智能爬虫配置
export function AISmartScraperConfig({ data, onChange, onBatchChange }: { data: NodeData; onChange: (key: string, value: unknown) => void; onBatchChange: BatchChange }) {
  return (
    <>
      <div className="p-3 bg-red-50 border-2 border-red-300 rounded-lg mb-4">
        <p className="text-sm text-red-900 font-semibold mb-2">实验性功能 - 不推荐生产使用</p>
        <p className="text-xs text-red-800">适合用自然语言从当前 CloakBrowser 页面提取内容；复杂结构优先使用确定性的元素提取节点。</p>
      </div>
      <AIModelPicker data={data} onBatchChange={onBatchChange} />
      <div className="space-y-2">
        <Label htmlFor="url">目标网页URL</Label>
        <VariableInput value={(data.url as string) || ''} onChange={(v) => onChange('url', v)} placeholder="https://example.com，支持 {变量名}" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="prompt">提取提示词</Label>
        <VariableInput value={(data.prompt as string) || ''} onChange={(v) => onChange('prompt', v)} placeholder='示例：提取前10项并返回JSON数组' multiline rows={4} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="waitTime">页面加载等待时间 (秒)</Label>
        <NumberInput id="waitTime" value={(data.waitTime as number) ?? 3} onChange={(v) => onChange('waitTime', v)} defaultValue={3} min={0} max={30} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput id="variableName" value={(data.variableName as string) || ''} onChange={(v) => onChange('variableName', v)} placeholder="变量名" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="verbose">详细日志</Label>
        <Select id="verbose" value={String(data.verbose ?? false)} onChange={(e) => onChange('verbose', e.target.value === 'true')}>
          <option value="false">否</option><option value="true">是</option>
        </Select>
      </div>
      <div className="bg-[hsl(var(--card))] p-3 border border-purple-200 rounded-lg">
        <p className="text-xs text-purple-900"><strong className="inline-flex items-center gap-1.5"><Bot className="w-3.5 h-3.5" />AI智能爬虫</strong><br/>使用主应用模型分析 CloakBrowser 已加载的页面，不启动第二套浏览器。</p>
      </div>
    </>
  )
}

// AI智能元素选择器配置
export function AIElementSelectorConfig({ data, onChange, onBatchChange }: { data: NodeData; onChange: (key: string, value: unknown) => void; onBatchChange: BatchChange }) {
  return (
    <>
      <div className="p-3 bg-red-50 border-2 border-red-300 rounded-lg mb-4">
        <p className="text-sm text-red-900 font-semibold mb-2">实验性功能 - 不推荐生产使用</p>
        <p className="text-xs text-red-800">AI 返回的选择器必须再用定位测试验证；稳定页面优先使用元素拾取。</p>
      </div>
      <AIModelPicker data={data} onBatchChange={onBatchChange} />
      <div className="space-y-2">
        <Label htmlFor="url">目标网页URL</Label>
        <VariableInput value={(data.url as string) || ''} onChange={(v) => onChange('url', v)} placeholder="https://example.com，支持 {变量名}" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="elementDescription">元素描述</Label>
        <VariableInput value={(data.elementDescription as string) || ''} onChange={(v) => onChange('elementDescription', v)} placeholder="如：登录按钮、搜索输入框" multiline rows={3} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="waitTime">页面加载等待时间 (秒)</Label>
        <NumberInput id="waitTime" value={(data.waitTime as number) ?? 3} onChange={(v) => onChange('waitTime', v)} defaultValue={3} min={0} max={30} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储选择器到变量</Label>
        <VariableNameInput id="variableName" value={(data.variableName as string) || ''} onChange={(v) => onChange('variableName', v)} placeholder="变量名" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="verbose">详细日志</Label>
        <Select id="verbose" value={String(data.verbose ?? false)} onChange={(e) => onChange('verbose', e.target.value === 'true')}>
          <option value="false">否</option><option value="true">是</option>
        </Select>
      </div>
      <div className="bg-[hsl(var(--card))] p-3 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-900"><strong>AI智能元素选择器</strong><br/>使用主应用模型分析 CloakBrowser 已加载页面并返回 CSS 选择器。</p>
      </div>
    </>
  )
}

// Firecrawl AI 单页数据抓取配置
export function FirecrawlScrapeConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="url">目标URL</Label>
        <VariableInput
          value={(data.url as string) || ''}
          onChange={(v) => onChange('url', v)}
          placeholder="https://example.com，支持 {变量名}"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="scrape_result"
          isStorageVariable={true}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="formats">返回格式</Label>
        <div className="space-y-1">
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(data.formats as string[] || ['markdown']).includes('markdown')}
              onCheckedChange={(c) => {
                const formats = (data.formats as string[] || ['markdown'])
                if (c) {
                  onChange('formats', [...formats, 'markdown'])
                } else {
                  onChange('formats', formats.filter(f => f !== 'markdown'))
                }
              }}
            />
            <span className="text-sm">Markdown</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(data.formats as string[] || []).includes('html')}
              onCheckedChange={(c) => {
                const formats = (data.formats as string[] || ['markdown'])
                if (c) {
                  onChange('formats', [...formats, 'html'])
                } else {
                  onChange('formats', formats.filter(f => f !== 'html'))
                }
              }}
            />
            <span className="text-sm">HTML</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(data.formats as string[] || []).includes('screenshot')}
              onCheckedChange={(c) => {
                const formats = (data.formats as string[] || ['markdown'])
                if (c) {
                  onChange('formats', [...formats, 'screenshot'])
                } else {
                  onChange('formats', formats.filter(f => f !== 'screenshot'))
                }
              }}
            />
            <span className="text-sm">Screenshot</span>
          </label>
        </div>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="onlyMainContent">只提取主要内容</Label>
        <Select
          id="onlyMainContent"
          value={String(data.onlyMainContent ?? true)}
          onChange={(e) => onChange('onlyMainContent', e.target.value === 'true')}
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="includeTags">包含标签 (可选)</Label>
        <VariableInput
          value={(data.includeTags as string) || ''}
          onChange={(v) => onChange('includeTags', v)}
          placeholder="article, main, .content (逗号分隔)"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="excludeTags">排除标签 (可选)</Label>
        <VariableInput
          value={(data.excludeTags as string) || ''}
          onChange={(v) => onChange('excludeTags', v)}
          placeholder="nav, footer, .ads (逗号分隔)"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="waitFor">等待选择器 (可选)</Label>
        <VariableInput
          value={(data.waitFor as string) || ''}
          onChange={(v) => onChange('waitFor', v)}
          placeholder="#content-ready，最多等待 5 秒"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="timeout">超时时间 (毫秒)</Label>
        <NumberInput
          id="timeout"
          value={(data.timeout as number) ?? 60000}
          onChange={(v) => onChange('timeout', v)}
          defaultValue={60000}
          min={1000}
        />
      </div>
      
      <div className="bg-[hsl(var(--card))] p-3 border border-orange-200 rounded-lg">
        <p className="text-xs text-orange-900">
          <strong>Firecrawl AI 单页数据抓取</strong><br/>
          • 智能提取网页结构化数据<br />
          • 支持 Markdown、HTML、截图等格式<br />
          • 自动处理 JavaScript 渲染<br />
          • 过滤广告和无关内容
        </p>
      </div>
    </>
  )
}

// Firecrawl AI 网站链接抓取配置
export function FirecrawlMapConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="url">目标URL</Label>
        <VariableInput
          value={(data.url as string) || ''}
          onChange={(v) => onChange('url', v)}
          placeholder="https://example.com，支持 {变量名}"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="variableName">存储链接列表到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="map_result"
          isStorageVariable={true}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="search">搜索关键词 (可选)</Label>
        <VariableInput
          value={(data.search as string) || ''}
          onChange={(v) => onChange('search', v)}
          placeholder="只返回包含关键词的链接，支持 {变量名}"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="limit">链接数量限制</Label>
        <NumberInput
          id="limit"
          value={(data.limit as number) ?? 5000}
          onChange={(v) => onChange('limit', v)}
          defaultValue={5000}
          min={1}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="ignoreSitemap">忽略 Sitemap</Label>
        <Select
          id="ignoreSitemap"
          value={String(data.ignoreSitemap ?? false)}
          onChange={(e) => onChange('ignoreSitemap', e.target.value === 'true')}
        >
          <option value="false">否</option>
          <option value="true">是</option>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="includeSubdomains">包含子域名</Label>
        <Select
          id="includeSubdomains"
          value={String(data.includeSubdomains ?? false)}
          onChange={(e) => onChange('includeSubdomains', e.target.value === 'true')}
        >
          <option value="false">否</option>
          <option value="true">是</option>
        </Select>
      </div>
      
      <div className="bg-[hsl(var(--card))] p-3 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-900">
          <strong>🗺️ Firecrawl AI 网站链接抓取</strong><br/>
          • 智能发现网站的所有链接<br />
          • 可用于构建网站地图<br />
          • 支持关键词过滤<br />
          • 返回链接数组，可配合循环使用
        </p>
      </div>
    </>
  )
}

// Firecrawl AI 全站数据抓取配置
export function FirecrawlCrawlConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="url">目标URL</Label>
        <VariableInput
          value={(data.url as string) || ''}
          onChange={(v) => onChange('url', v)}
          placeholder="https://example.com，支持 {变量名}"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="crawl_result"
          isStorageVariable={true}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="maxDepth">最大爬取深度</Label>
        <NumberInput
          id="maxDepth"
          value={(data.maxDepth as number) ?? 2}
          onChange={(v) => onChange('maxDepth', v)}
          defaultValue={2}
          min={1}
          max={10}
        />
        <p className="text-xs text-muted-foreground">
          深度越大，爬取的页面越多，耗时越长
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="limit">页面数量限制</Label>
        <NumberInput
          id="limit"
          value={(data.limit as number) ?? 100}
          onChange={(v) => onChange('limit', v)}
          defaultValue={100}
          min={1}
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="includePaths">包含路径 (可选)</Label>
        <VariableInput
          value={(data.includePaths as string) || ''}
          onChange={(v) => onChange('includePaths', v)}
          placeholder="/blog, /docs (逗号分隔)"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="excludePaths">排除路径 (可选)</Label>
        <VariableInput
          value={(data.excludePaths as string) || ''}
          onChange={(v) => onChange('excludePaths', v)}
          placeholder="/admin, /login (逗号分隔)"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="formats">返回格式</Label>
        <div className="space-y-1">
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(data.formats as string[] || ['markdown']).includes('markdown')}
              onCheckedChange={(c) => {
                const formats = (data.formats as string[] || ['markdown'])
                if (c) {
                  onChange('formats', [...formats, 'markdown'])
                } else {
                  onChange('formats', formats.filter(f => f !== 'markdown'))
                }
              }}
            />
            <span className="text-sm">Markdown</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox
              checked={(data.formats as string[] || []).includes('html')}
              onCheckedChange={(c) => {
                const formats = (data.formats as string[] || ['markdown'])
                if (c) {
                  onChange('formats', [...formats, 'html'])
                } else {
                  onChange('formats', formats.filter(f => f !== 'html'))
                }
              }}
            />
            <span className="text-sm">HTML</span>
          </label>
        </div>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="onlyMainContent">只提取主要内容</Label>
        <Select
          id="onlyMainContent"
          value={String(data.onlyMainContent ?? true)}
          onChange={(e) => onChange('onlyMainContent', e.target.value === 'true')}
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="ignoreSitemap">忽略 Sitemap</Label>
        <Select
          id="ignoreSitemap"
          value={String(data.ignoreSitemap ?? false)}
          onChange={(e) => onChange('ignoreSitemap', e.target.value === 'true')}
        >
          <option value="false">否</option>
          <option value="true">是</option>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="allowBackwardLinks">允许回退链接</Label>
        <Select
          id="allowBackwardLinks"
          value={String(data.allowBackwardLinks ?? false)}
          onChange={(e) => onChange('allowBackwardLinks', e.target.value === 'true')}
        >
          <option value="false">否</option>
          <option value="true">是</option>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="allowExternalLinks">允许外部链接</Label>
        <Select
          id="allowExternalLinks"
          value={String(data.allowExternalLinks ?? false)}
          onChange={(e) => onChange('allowExternalLinks', e.target.value === 'true')}
        >
          <option value="false">否</option>
          <option value="true">是</option>
        </Select>
      </div>
      
      <div className="bg-[hsl(var(--card))] p-3 border border-purple-200 rounded-lg">
        <p className="text-xs text-purple-900">
          <strong>🕷️ Firecrawl AI 全站数据抓取</strong><br/>
          • 智能爬取整个网站的数据<br />
          • 支持深度爬取和智能过滤<br />
          • 自动处理分页和动态加载<br />
          • 注意：全站爬取可能需要几分钟
        </p>
      </div>
    </>
  )
}


// ============================================================
// AI 数据处理任务（抽取/分类/摘要/翻译/情感）通用配置面板
// 复用全局 AI 模型选择 + API 字段，按 moduleType 渲染任务专属字段。
// ============================================================
function AITaskApiBlock({ data, onBatchChange }: { data: NodeData; onBatchChange: BatchChange }) {
  return <AIModelPicker data={data} onBatchChange={onBatchChange} />
}

export function AITaskConfig({ moduleType, data, onChange, onBatchChange }: { moduleType: string; data: NodeData; onChange: (key: string, value: unknown) => void; onBatchChange: BatchChange }) {
  return (
    <div className="space-y-3">
      {moduleType === 'ai_dedup_semantic' ? (
        <div className="space-y-2">
          <Label htmlFor="inputList">待去重列表</Label>
          <VariableInput
            multiline
            rows={4}
            value={(data.inputList as string) || ''}
            onChange={(v) => onChange('inputList', v)}
            placeholder='数组变量 {list} 或 JSON 数组 ["苹果手机","iPhone",...]（建议≤300项）'
          />
          <p className="text-xs text-muted-foreground">会合并语义相同但表达不同的项，保留首个；结果为去重后数组。</p>
        </div>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="inputText">输入文本</Label>
          <VariableInput
            multiline
            rows={4}
            value={(data.inputText as string) || ''}
            onChange={(v) => onChange('inputText', v)}
            placeholder="要处理的文本，支持 {变量名}（如 {data}、{ai_response}）"
          />
        </div>
      )}

      {moduleType === 'ai_extract' && (
        <div className="space-y-2">
          <Label htmlFor="fields">要抽取的字段</Label>
          <VariableInput
            value={(data.fields as string) || ''}
            onChange={(v) => onChange('fields', v)}
            placeholder='如 姓名,电话,地址  或  {"name":"姓名","price":"价格(数字)"}'
          />
          <p className="text-xs text-muted-foreground">逗号分隔字段名，或用 JSON 描述每个字段含义。结果为 JSON 对象。</p>
        </div>
      )}

      {moduleType === 'ai_classify' && (
        <div className="space-y-2">
          <Label htmlFor="categories">候选类别</Label>
          <VariableInput
            value={(data.categories as string) || ''}
            onChange={(v) => onChange('categories', v)}
            placeholder="如 投诉,咨询,好评,其他（逗号分隔，至少两个）"
          />
          <p className="text-xs text-muted-foreground">结果为命中的类别名（字符串）。</p>
        </div>
      )}

      {moduleType === 'ai_summarize' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="maxWords">摘要最大字数</Label>
            <NumberInput
              id="maxWords"
              value={(data.maxWords as number) ?? 200}
              onChange={(v) => onChange('maxWords', v)}
              defaultValue={200}
              min={20}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="style">风格要求（可选）</Label>
            <VariableInput
              value={(data.style as string) || ''}
              onChange={(v) => onChange('style', v)}
              placeholder="如 要点列表 / 一句话 / 商务正式"
            />
          </div>
        </>
      )}

      {moduleType === 'ai_translate' && (
        <div className="space-y-2">
          <Label htmlFor="targetLang">目标语言</Label>
          <VariableInput
            value={(data.targetLang as string) || ''}
            onChange={(v) => onChange('targetLang', v)}
            placeholder="如 英文 / 日文 / 法文 / 中文"
          />
        </div>
      )}

      {moduleType === 'ai_normalize' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="normalizeType">规整类型</Label>
            <Select
              value={(data.normalizeType as string) || 'date'}
              onChange={(e) => onChange('normalizeType', e.target.value)}
            >
              <option value="date">日期/时间 → 标准格式</option>
              <option value="money">金额 → 纯数字</option>
              <option value="phone">电话 → 标准格式</option>
              <option value="number">数值 → 纯数字</option>
              <option value="name">人名规整</option>
              <option value="address">地址规整</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="targetFormat">自定义目标格式（可选）</Label>
            <VariableInput
              value={(data.targetFormat as string) || ''}
              onChange={(v) => onChange('targetFormat', v)}
              placeholder="如 YYYY-MM-DD HH:mm:ss；留空用该类型默认格式"
            />
          </div>
        </>
      )}

      {moduleType === 'ai_route' && (
        <div className="space-y-2">
          <Label htmlFor="routes">分支选项</Label>
          <VariableInput
            multiline
            rows={4}
            value={(data.routes as string) || ''}
            onChange={(v) => onChange('routes', v)}
            placeholder={'每行一个，名称:说明，例如\n退款:用户要求退钱\n咨询:用户询问信息\n投诉:用户表达不满'}
          />
          <p className="text-xs text-muted-foreground">结果为命中的分支名（字符串）；后接「条件分支」按它路由。</p>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="结果变量名"
          isStorageVariable={true}
        />
      </div>

      <details className="rounded-lg border border-[hsl(var(--border))] p-2">
        <summary className="text-sm cursor-pointer select-none text-[hsl(var(--muted-foreground))]">AI 模型设置</summary>
        <div className="space-y-2 mt-2">
          <AITaskApiBlock data={data} onBatchChange={onBatchChange} />
        </div>
      </details>
    </div>
  )
}

// AI视觉操作配置（看当前页面点选，不依赖选择器）
export function AIVisionActConfig({ data, onChange, onBatchChange }: { data: NodeData; onChange: (key: string, value: unknown) => void; onBatchChange: BatchChange }) {
  const action = (data.action as string) || 'click'
  const needButton = action === 'click' || action === 'double'
  return (
    <>
      <AIModelPicker data={data} onBatchChange={onBatchChange} />

      <div className="space-y-2">
        <Label htmlFor="instruction">目标描述</Label>
        <VariableInput
          value={(data.instruction as string) || ''}
          onChange={(v) => onChange('instruction', v)}
          placeholder="用自然语言描述要点击的目标，如：右上角的登录按钮"
          multiline
          rows={3}
        />
        <p className="text-xs text-muted-foreground">AI 会截取当前浏览器页面，根据描述定位目标并返回坐标。</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="action">执行动作</Label>
        <Select
          id="action"
          value={action}
          onChange={(e) => onChange('action', e.target.value)}
        >
          <option value="click">单击</option>
          <option value="double">双击</option>
          <option value="right">右键单击</option>
          <option value="move">仅移动鼠标</option>
          <option value="locate">仅定位（不操作，返回坐标）</option>
        </Select>
      </div>
      {needButton && (
        <div className="space-y-2">
          <Label htmlFor="button">鼠标按键</Label>
          <Select
            id="button"
            value={(data.button as string) || 'left'}
            onChange={(e) => onChange('button', e.target.value)}
          >
            <option value="left">左键</option>
            <option value="right">右键</option>
            <option value="middle">中键</option>
          </Select>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="variableName">存储坐标到变量</Label>
        <VariableNameInput
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="结果变量名，存储 {x, y} 坐标"
          isStorageVariable={true}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="maxTokens">最大Token数</Label>
        <NumberInput
          id="maxTokens"
          value={(data.maxTokens as number) ?? 300}
          onChange={(v) => onChange('maxTokens', v)}
          defaultValue={300}
          min={1}
        />
      </div>
      <div className="p-3 bg-violet-50 border border-violet-200 rounded-lg">
        <p className="text-xs text-violet-800">
          <strong>AI视觉操作</strong>让 AI 直接"看页面"定位目标并真实点击，无需任何选择器。<br/>
          • 适合 Canvas、图片按钮、防自动化页面等取不到选择器的场景<br/>
          • 操作仅限当前 CloakBrowser 页面，不控制 Windows 桌面
        </p>
      </div>
    </>
  )
}
