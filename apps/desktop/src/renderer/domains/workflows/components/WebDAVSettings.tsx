// Source: WebRPA@5ccb900e, components/workflow/WebDAVSettings.tsx; see SOURCE.md for license and adaptation boundaries.
import { getStudioTransportRevision } from '../api/transport'
import { apiRequest } from '../api'
import { useEffect, useState, useRef } from 'react'
import { Loader2, Wifi, Save as SaveIcon } from 'lucide-react'
import { Switch } from './controls/switch'

interface WebDAVConfig {
  enabled: boolean
  url: string
  username: string
  password: string
  remoteDir: string
}

const EMPTY: WebDAVConfig = { enabled: false, url: '', username: '', password: '', remoteDir: '' }

/**
 * WebDAV 设置：让工作流的保存/读取走 WebDAV（NAS、Nextcloud、坚果云等），实现多端共享。
 */
export function WebDAVSettings() {
  const [cfg, setCfg] = useState<WebDAVConfig>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const request = useRef(0)
  const busy = useRef(false)

  useEffect(() => {
    const invalidate = () => {
      request.current++; busy.current = false
      setLoading(false); setSaving(false); setTesting(false); setMsg(null)
      setLoadError('连接已更换，请重新读取配置')
    }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => { request.current++; window.removeEventListener('studio:transport-changed', invalidate) }
  }, [])
  useEffect(() => {
    const sequence = ++request.current
    const revision = getStudioTransportRevision()
    const current = () => sequence === request.current && revision === getStudioTransportRevision()
    setLoading(true); setLoadError('')
    void (async () => {
      try {
        const result = await apiRequest<{config: unknown}>('/local-workflows/webdav-config')
        if (!current()) return
        if (!result.success) throw new Error(result.error || '读取配置失败')
        const raw = result.data?.config
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('WebDAV 配置格式错误')
        const next = {...EMPTY,...raw}
        if (typeof next.enabled !== 'boolean' || ['url','username','password','remoteDir'].some(key => typeof next[key as keyof WebDAVConfig] !== 'string')) throw new Error('WebDAV 配置格式错误')
        setCfg(next)
      } catch (error) { if (current()) setLoadError(error instanceof Error ? error.message : '读取配置失败') }
      finally { if (current()) setLoading(false) }
    })()
    return () => { request.current++ }
  }, [attempt])

  const update = (patch: Partial<WebDAVConfig>) => { setCfg(current => ({...current,...patch})); setMsg(null) }
  const submit = async (action: 'save' | 'test') => {
    if (busy.current || loading || loadError) return
    if (cfg.enabled || action === 'test') {
      try { const url = new URL(cfg.url); if (!['http:','https:'].includes(url.protocol)) throw new Error() }
      catch { setMsg({type:'err',text:'请输入有效的 HTTP 或 HTTPS WebDAV 地址'}); return }
    }
    busy.current = true
    const sequence = ++request.current
    const revision = getStudioTransportRevision()
    const current = () => sequence === request.current && revision === getStudioTransportRevision()
    setSaving(action === 'save'); setTesting(action === 'test'); setMsg(null)
    try {
      const result = await apiRequest<{success: boolean; mock?: boolean}>(action === 'save' ? '/local-workflows/webdav-config' : '/local-workflows/webdav-test', {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg),
      })
      if (!current()) return
      if (!result.success || result.data?.success !== true) throw new Error(result.error || (action === 'save' ? '保存失败' : '连接失败'))
      const text = result.data.mock
        ? (action === 'save' ? '已保存模拟配置，未连接远程存储' : '模拟测试返回，未验证远程连接')
        : action === 'test' ? '连接成功！' : cfg.enabled ? '配置已保存' : '已保存（WebDAV 未启用，仍用本地目录）'
      setMsg({type:'ok',text})
    } catch (error) { if (current()) setMsg({type:'err',text:error instanceof Error ? error.message : '操作失败'}) }
    finally { if (current()) { busy.current = false; setSaving(false); setTesting(false) } }
  }

  return (
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <label className="text-sm font-medium text-gray-700">WebDAV 远程存储（NAS / 网盘）</label>
          <p className="text-xs text-gray-500 mt-1">开启后，工作流的保存与读取都走 WebDAV 远程目录，可在多台设备间共享。</p>
        </div>
        <Switch disabled={loading || saving || testing || !!loadError} className="flex-none ml-3" checked={cfg.enabled} onCheckedChange={(c) => update({ enabled: c })} />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-gray-500"><Loader2 className="w-3.5 h-3.5 animate-spin" />读取配置…</div>
      ) : loadError ? (
        <div role="alert"><p className="text-xs text-red-600">{loadError}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>重试读取配置</button></div>
      ) : (
        <div className="space-y-2">
          <input disabled={saving || testing} value={cfg.url} onChange={(e) => update({ url: e.target.value })} placeholder="WebDAV 地址，如 https://dav.example.com/webrpa/"
            className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 bg-white text-black" />
          <div className="grid grid-cols-2 gap-2">
            <input disabled={saving || testing} value={cfg.username} onChange={(e) => update({ username: e.target.value })} placeholder="用户名"
              className="px-3 py-2 text-sm rounded-md border border-gray-300 bg-white text-black" />
            <input disabled={saving || testing} type="password" value={cfg.password} onChange={(e) => update({ password: e.target.value })} placeholder="密码"
              className="px-3 py-2 text-sm rounded-md border border-gray-300 bg-white text-black" />
          </div>
          <input disabled={saving || testing} value={cfg.remoteDir} onChange={(e) => update({ remoteDir: e.target.value })} placeholder="子目录（可选），如 workflows"
            className="w-full px-3 py-2 text-sm rounded-md border border-gray-300 bg-white text-black" />
          <div className="flex items-center gap-2">
            <button onClick={() => submit('test')} disabled={saving || testing || !cfg.url}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-gray-300 bg-white hover:bg-gray-100 text-gray-700 disabled:opacity-50">
              {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}测试连接
            </button>
            <button onClick={() => submit('save')} disabled={saving || testing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <SaveIcon className="w-3.5 h-3.5" />}保存配置
            </button>
            {msg && <span role={msg.type === 'err' ? 'alert' : 'status'} className={`text-xs ${msg.type === 'ok' ? 'text-green-600' : 'text-red-500'}`}>{msg.text}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
