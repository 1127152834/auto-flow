// Remediation M2 R2-28: cookie, page storage and request interception nodes.
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'

type Props = { data: NodeData; onChange: (key: string, value: unknown) => void }

function Field({ id, label, value, placeholder, hint, onChange }: { id: string; label: string; value: unknown; placeholder?: string; hint?: string; onChange(value: string): void }) {
  return <div className="space-y-2">
    <Label htmlFor={id}>{label}</Label>
    <VariableInput value={typeof value === 'string' ? value : ''} onChange={onChange} placeholder={placeholder}/>
    {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
  </div>
}

export function WebCookieConfig({ data, onChange }: Props) {
  const operation = (data.operation as string) || 'get'
  return <>
    <div className="space-y-2"><Label htmlFor="operation">操作</Label>
      <Select id="operation" aria-label="Cookie 操作" value={operation} onChange={event => onChange('operation', event.target.value)}>
        <option value="get">读取</option><option value="set">写入</option><option value="delete">删除</option><option value="clear">全部清空</option>
      </Select>
    </div>
    {operation !== 'clear' ? <Field id="name" label="名称" value={data.name} placeholder={operation === 'get' ? '留空读取全部' : '例如: session'} onChange={value => onChange('name', value)}/> : null}
    {operation === 'set' ? <Field id="value" label="值" value={data.value} onChange={value => onChange('value', value)}/> : null}
    {operation === 'set' || operation === 'get' ? <Field id="url" label="网址" value={data.url} placeholder="留空使用当前页面" onChange={value => onChange('url', value)}/> : null}
    {operation !== 'get' ? <Field id="domain" label="域名" value={data.domain} placeholder="可选，例如: .example.com" onChange={value => onChange('domain', value)}/> : null}
    {operation === 'get' ? <Field id="variableName" label="保存到变量" value={data.variableName} hint="读取到的 Cookie 会按敏感值保存，不会出现在日志里" onChange={value => onChange('variableName', value)}/> : null}
  </>
}

export function WebStorageConfig({ data, onChange }: Props) {
  const operation = (data.operation as string) || 'get'
  return <>
    <div className="space-y-2"><Label htmlFor="area">存储</Label>
      <Select id="area" aria-label="页面存储" value={(data.area as string) || 'local'} onChange={event => onChange('area', event.target.value)}>
        <option value="local">本地存储（localStorage）</option><option value="session">会话存储（sessionStorage）</option>
      </Select>
    </div>
    <div className="space-y-2"><Label htmlFor="operation">操作</Label>
      <Select id="operation" aria-label="存储操作" value={operation} onChange={event => onChange('operation', event.target.value)}>
        <option value="get">读取一项</option><option value="getAll">读取全部</option><option value="set">写入</option><option value="remove">删除一项</option><option value="clear">全部清空</option>
      </Select>
    </div>
    {['get', 'set', 'remove'].includes(operation) ? <Field id="key" label="键" value={data.key} onChange={value => onChange('key', value)}/> : null}
    {operation === 'set' ? <Field id="value" label="值" value={data.value} onChange={value => onChange('value', value)}/> : null}
    {operation === 'get' || operation === 'getAll' ? <Field id="variableName" label="保存到变量" value={data.variableName} hint="读取到的值按敏感值保存" onChange={value => onChange('variableName', value)}/> : null}
  </>
}

export function WebInterceptConfig({ data, onChange }: Props) {
  const operation = (data.operation as string) || 'start'
  const action = (data.action as string) || 'block'
  return <>
    <div className="space-y-2"><Label htmlFor="operation">操作</Label>
      <Select id="operation" aria-label="拦截操作" value={operation} onChange={event => onChange('operation', event.target.value)}>
        <option value="start">开始拦截</option><option value="stop">停止拦截</option>
      </Select>
    </div>
    <Field id="urlPattern" label="网址规则" value={data.urlPattern} placeholder="例如: **/api/orders**" hint="停止时填写与开始时相同的规则" onChange={value => onChange('urlPattern', value)}/>
    {operation === 'start' ? <div className="space-y-2"><Label htmlFor="action">处理方式</Label>
      <Select id="action" aria-label="拦截方式" value={action} onChange={event => onChange('action', event.target.value)}>
        <option value="block">阻止请求</option><option value="mock">返回模拟数据</option><option value="headers">添加请求头后放行</option>
      </Select>
    </div> : null}
    {operation === 'start' && action === 'mock' ? <>
      <Field id="mockStatus" label="状态码" value={data.mockStatus === undefined ? '200' : String(data.mockStatus)} onChange={value => onChange('mockStatus', value)}/>
      <Field id="mockContentType" label="内容类型" value={data.mockContentType} placeholder="application/json" onChange={value => onChange('mockContentType', value)}/>
      <Field id="mockBody" label="返回内容" value={data.mockBody} onChange={value => onChange('mockBody', value)}/>
    </> : null}
    {operation === 'start' && action === 'headers' ? <Field id="headers" label="请求头（JSON）" value={typeof data.headers === 'string' ? data.headers : data.headers ? JSON.stringify(data.headers) : ''} placeholder='{"X-Trace": "1"}' onChange={value => { try { onChange('headers', JSON.parse(value)) } catch { onChange('headers', value) } }}/> : null}
  </>
}
