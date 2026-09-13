// Source: WebRPA@5ccb900e, components/workflow/config-panels/WebhookModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../controls/select'
import { Textarea } from '../controls/textarea'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { NumberInput } from '../controls/number-input'
import { Switch } from '../controls/switch'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// Webhook请求配置
export function WebhookRequestConfig({ data, onChange }: ConfigProps) {
  const method = (data.method as string) || 'POST'
  const hasBody = ['POST', 'PUT', 'PATCH'].includes(method)

  return (
    <div className="space-y-4">
      {/* 请求URL */}
      <div className="space-y-2">
        <Label>请求 URL</Label>
        <VariableInput
          value={(data.url as string) || ''}
          onChange={(v) => onChange('url', v)}
          placeholder="https://api.example.com/webhook"
        />
      </div>

      {/* 请求方法 */}
      <div className="space-y-2">
        <Label>请求方法</Label>
        <Select
          value={method}
          onValueChange={(v) => onChange('method', v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择请求方法" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="GET">GET</SelectItem>
            <SelectItem value="POST">POST</SelectItem>
            <SelectItem value="PUT">PUT</SelectItem>
            <SelectItem value="PATCH">PATCH</SelectItem>
            <SelectItem value="DELETE">DELETE</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* 请求头 */}
      <div className="space-y-2">
        <Label>请求头（JSON 格式）</Label>
        <Textarea
          value={(data.headers as string) || ''}
          onChange={(e) => onChange('headers', e.target.value)}
          placeholder={'{"Authorization": "Bearer {token}", "Content-Type": "application/json"}'}
          rows={3}
          className="font-mono text-xs"
        />
      </div>

      {/* Cookies */}
      <div className="space-y-2">
        <Label>Cookies</Label>
        <Textarea
          value={(data.cookies as string) || ''}
          onChange={(e) => onChange('cookies', e.target.value)}
          placeholder={'JSON格式：{"session": "abc123"}\n或键值对格式：session=abc123; token=xyz'}
          rows={3}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          支持 JSON 格式或 <code>key=value; key2=value2</code> 格式，支持变量引用
        </p>
      </div>

      {/* 请求体（仅 POST/PUT/PATCH 显示） */}
      {hasBody && (
        <>
          <div className="space-y-2">
            <Label>请求体格式</Label>
            <Select
              value={(data.bodyType as string) || 'json'}
              onValueChange={(v) => onChange('bodyType', v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择请求体格式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="json">JSON</SelectItem>
                <SelectItem value="form">表单（Form）</SelectItem>
                <SelectItem value="raw">原始文本</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>请求体内容</Label>
            <Textarea
              value={(data.body as string) || ''}
              onChange={(e) => onChange('body', e.target.value)}
              placeholder={'{"key": "value", "name": "{变量名}"}'}
              rows={5}
              className="font-mono text-xs"
            />
          </div>
        </>
      )}

      {/* 超时时间 */}
      <div className="space-y-2">
        <Label>超时时间（秒）</Label>
        <NumberInput
          value={(data.timeout as number) || 30}
          onChange={(v) => onChange('timeout', v)}
          defaultValue={30}
          min={1}
          max={600}
        />
      </div>

      {/* SSL 验证 */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">验证 SSL 证书</Label>
          <p className="text-xs text-muted-foreground">关闭后可访问自签名证书的 HTTPS 接口</p>
        </div>
        <Switch
          checked={(data.verifySSL as boolean) !== false}
          onCheckedChange={(v) => onChange('verifySSL', v)}
        />
      </div>

      {/* 跟随重定向 */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">跟随重定向</Label>
          <p className="text-xs text-muted-foreground">自动跟随 3xx 重定向响应</p>
        </div>
        <Switch
          checked={(data.followRedirects as boolean) !== false}
          onCheckedChange={(v) => onChange('followRedirects', v)}
        />
      </div>

      {/* 保存响应内容 */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">保存响应内容</Label>
          <p className="text-xs text-muted-foreground">将响应体保存到变量</p>
        </div>
        <Switch
          checked={(data.saveResponse as boolean) || false}
          onCheckedChange={(v) => onChange('saveResponse', v)}
        />
      </div>
      {!!(data.saveResponse) && (
        <div className="space-y-2">
          <Label>响应内容变量名</Label>
          <VariableNameInput
            value={(data.responseVariable as string) || 'webhook_response'}
            onChange={(v) => onChange('responseVariable', v)}
            placeholder="webhook_response"
          />
        </div>
      )}

      {/* 保存状态码 */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">保存状态码</Label>
          <p className="text-xs text-muted-foreground">将 HTTP 状态码保存到变量</p>
        </div>
        <Switch
          checked={(data.saveStatus as boolean) || false}
          onCheckedChange={(v) => onChange('saveStatus', v)}
        />
      </div>
      {!!(data.saveStatus) && (
        <div className="space-y-2">
          <Label>状态码变量名</Label>
          <VariableNameInput
            value={(data.statusVariable as string) || 'webhook_status'}
            onChange={(v) => onChange('statusVariable', v)}
            placeholder="webhook_status"
          />
        </div>
      )}

      {/* 保存响应头 */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">保存响应头</Label>
          <p className="text-xs text-muted-foreground">将响应头保存到变量</p>
        </div>
        <Switch
          checked={(data.saveHeaders as boolean) || false}
          onCheckedChange={(v) => onChange('saveHeaders', v)}
        />
      </div>
      {!!(data.saveHeaders) && (
        <div className="space-y-2">
          <Label>响应头变量名</Label>
          <VariableNameInput
            value={(data.headersVariable as string) || 'webhook_headers'}
            onChange={(v) => onChange('headersVariable', v)}
            placeholder="webhook_headers"
          />
        </div>
      )}

      {/* 保存响应 Cookies */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm">保存响应 Cookies</Label>
          <p className="text-xs text-muted-foreground">将响应中的 Cookies 保存到变量</p>
        </div>
        <Switch
          checked={(data.saveCookies as boolean) || false}
          onCheckedChange={(v) => onChange('saveCookies', v)}
        />
      </div>
      {!!(data.saveCookies) && (
        <div className="space-y-2">
          <Label>响应 Cookies 变量名</Label>
          <VariableNameInput
            value={(data.cookiesVariable as string) || 'webhook_cookies'}
            onChange={(v) => onChange('cookiesVariable', v)}
            placeholder="webhook_cookies"
          />
        </div>
      )}
    </div>
  )
}
