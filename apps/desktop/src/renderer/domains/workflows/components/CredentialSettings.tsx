// Extracted from the migrated WebRPA GlobalConfigDialog; see SOURCE.md for attribution.
import { useSettingsDraftProtection, type RegisterSettingsLeaveGuard } from '../hooks/useSettingsDraftProtection'
import { useState, useEffect, useRef, useCallback } from 'react'
import { getStudioTransportRevision } from '../api/transport'
import { credentialApi, type CredentialItem } from '../api'
import { useConfirm } from './controls/confirm-dialog'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { Label } from './controls/label'
import { Plus, Trash2, RotateCcw } from 'lucide-react'

// 凭据库设置面板：管理本地加密凭据（口令/API Key/数据库密码等），节点里用 {{cred:名称.字段}} 引用
export function CredentialSettings({ registerLeaveGuard }: { registerLeaveGuard?: RegisterSettingsLeaveGuard }) {
  const [list, setList] = useState<CredentialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [mock, setMock] = useState(false)
  const busyRef = useRef(false)
  const mounted = useRef(true)
  const reads = useRef(0)
  const editingRevision = useRef(0)
  const initialEdit = useRef('')
  const [editing, setEditing] = useState<{ name: string; description: string; fields: { key: string; value: string }[] } | null>(null)
  const { confirm, alert, ConfirmDialog } = useConfirm()

  const refresh = useCallback(async () => {
    const sequence = ++reads.current
    const revision = getStudioTransportRevision()
    const current = () => mounted.current && sequence === reads.current && revision === getStudioTransportRevision()
    setLoading(true)
    setLoadError('')
    try {
      const res = await credentialApi.list()
      if (!current()) return
      const value = res.data
      if (!res.success || value?.success !== true || !Array.isArray(value.credentials) ||
          !value.credentials.every(c => c && ['name', 'description', 'created_at', 'updated_at'].every(key => typeof c[key as keyof CredentialItem] === 'string') &&
            Array.isArray(c.fields) && c.fields.every(f => f && typeof f.key === 'string' && typeof f.masked === 'string'))) {
        throw new Error(res.error || '凭据列表响应格式错误')
      }
      setList(value.credentials)
      setMock(value.mock === true)
      setLoaded(true)
    } catch (error) {
      if (current()) { setLoadError(`读取凭据失败：${error instanceof Error ? error.message : String(error)}`); setLoaded(false) }
    } finally { if (current()) setLoading(false) }
  }, [])
  useEffect(() => {
    mounted.current = true
    void refresh()
    const invalidate = () => {
      reads.current++
      setLoaded(false)
      setLoading(false)
      busyRef.current = false
      setBusy(false)
      setLoadError('服务连接已变更，请刷新凭据列表。已有编辑内容保留。')
    }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => { mounted.current = false; reads.current++; window.removeEventListener('studio:transport-changed', invalidate) }
  }, [refresh])

  const startNew = () => {
    editingRevision.current = getStudioTransportRevision()
    const initial = { name: '', description: '', fields: [{ key: 'value', value: '' }] }
    initialEdit.current = JSON.stringify(initial)
    setEditing(initial)
  }
  const startEdit = (c: CredentialItem) => {
    editingRevision.current = getStudioTransportRevision()
    const initial = { name: c.name, description: c.description,
      fields: c.fields.length ? c.fields.map(f => ({ key: f.key, value: '' })) : [{ key: 'value', value: '' }] }
    initialEdit.current = JSON.stringify(initial)
    setEditing(initial)
  }

  const save = async () => {
    if (!editing || busyRef.current || !loaded) return false
    const revision = getStudioTransportRevision()
    if (editingRevision.current !== revision) return false
    if (!editing.name.trim()) { await alert('请填写凭据名', { title: '提示' }); return false }
    const entries = editing.fields.map(f => [f.key.trim(), f.value] as const)
    if (!entries.length) { await alert('至少需要一个字段', { title: '提示' }); return false }
    if (entries.some(([key]) => !key)) { await alert('字段名不能为空', { title: '提示' }); return false }
    if (new Set(entries.map(([key]) => key)).size !== entries.length) { await alert('字段名重复，请修改后保存', { title: '提示' }); return false }
    busyRef.current = true
    setBusy(true)
    const current = () => mounted.current && revision === getStudioTransportRevision()
    try {
      const res = await credentialApi.upsert(editing.name.trim(), Object.fromEntries(entries), editing.description)
      if (!current()) return false
      if (!res.success || res.data?.success !== true) { await alert(`保存失败：${res.error || '服务未返回有效确认'}`, { title: '失败' }); return false }
      setEditing(null)
      await refresh()
      return current()
    } finally { if (current()) { busyRef.current = false; setBusy(false) } }
  }

  const del = async (name: string) => {
    if (busyRef.current || !loaded) return
    const revision = getStudioTransportRevision()
    const current = () => mounted.current && revision === getStudioTransportRevision()
    busyRef.current = true
    setBusy(true)
    try {
      const ok = await confirm(`删除凭据「${name}」？引用它的工作流将无法解析。`, { type: 'warning', title: '删除凭据', confirmText: '删除', cancelText: '取消' })
      if (!ok || !current()) return
      const result = await credentialApi.delete(name)
      if (!current()) return
      if (!result.success || result.data?.success !== true) { await alert(`删除失败：${result.error || '服务未返回有效确认'}`, { title: '失败' }); return }
      await refresh()
    } finally { if (current()) { busyRef.current = false; setBusy(false) } }
  }

  const leave = useSettingsDraftProtection(registerLeaveGuard, '保存凭据编辑？', !!editing && JSON.stringify(editing) !== initialEdit.current, busy, save)

  return (
    <>
      {loading && <p role="status">正在读取凭据…</p>}
      {loadError && <div role="alert">{loadError} <button disabled={loading || busy} onClick={() => void refresh()} aria-label="重试读取凭据">重试</button></div>}
      {editing && editingRevision.current !== getStudioTransportRevision() && <p role="alert">连接已变更，请取消当前编辑后重新选择凭据，原输入不会发送到新服务。</p>}
      {mock && <p>当前为 Mock：仅保存名称和打码字段信息，不保存或验证凭据值。</p>}
      <p className="text-xs text-gray-500 mb-4">
        列表仅展示打码字段，编辑时不会读取原值。在节点字符串中用
        <code className="bg-gray-100 px-1 rounded mx-1">{'{{cred:名称}}'}</code> 或
        <code className="bg-gray-100 px-1 rounded mx-1">{'{{cred:名称.字段}}'}</code> 引用，正式运行时由服务解析。
      </p>
      {editing ? (
        <fieldset disabled={busy || leave.pending} className="space-y-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-gray-700 text-xs">凭据名</Label>
              <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} placeholder="如：我的邮箱" className="bg-white text-black border-gray-300 h-8 text-sm mt-1" />
            </div>
            <div>
              <Label className="text-gray-700 text-xs">说明（可选）</Label>
              <Input value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} placeholder="用途备注" className="bg-white text-black border-gray-300 h-8 text-sm mt-1" />
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-gray-700 text-xs">字段（字段名 → 值；编辑时留空表示保留原值）</Label>
            {editing.fields.map((f, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input value={f.key} onChange={(e) => { const fs = [...editing.fields]; fs[i] = { ...fs[i], key: e.target.value }; setEditing({ ...editing, fields: fs }) }} placeholder="字段名 如 value/password/api_key" className="bg-white text-black border-gray-300 h-8 text-sm w-1/3" />
                <Input type="password" value={f.value} onChange={(e) => { const fs = [...editing.fields]; fs[i] = { ...fs[i], value: e.target.value }; setEditing({ ...editing, fields: fs }) }} placeholder="值" className="bg-white text-black border-gray-300 h-8 text-sm flex-1" />
                <button onClick={() => setEditing({ ...editing, fields: editing.fields.filter((_, j) => j !== i) })} className="p-1 text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => setEditing({ ...editing, fields: [...editing.fields, { key: '', value: '' }] })} className="border-gray-300 text-gray-700 hover:bg-gray-100">
              <Plus className="w-4 h-4 mr-1" />添加字段
            </Button>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setEditing(null)} className="border-gray-300 text-gray-700">取消</Button>
            <Button type="button" size="sm" disabled={busy || !loaded || editingRevision.current !== getStudioTransportRevision()} onClick={save}>保存</Button>
          </div>
        </fieldset>
      ) : (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Button type="button" variant="outline" size="sm" disabled={busy || loading || !loaded} onClick={startNew} className="border-gray-300 text-gray-700 hover:bg-gray-100"><Plus className="w-4 h-4 mr-1" />新增凭据</Button>
            <Button type="button" variant="outline" size="sm" aria-label="刷新凭据" onClick={() => void refresh()} disabled={loading || busy} className="border-gray-300 text-gray-700"><RotateCcw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /></Button>
          </div>
          {!loaded || loading ? null : list.length === 0 ? (
            <p className="text-xs text-gray-400 py-8 text-center">还没有凭据，点「新增凭据」创建</p>
          ) : list.map((c) => (
            <div key={c.name} className="p-3 bg-gray-50 rounded-lg border border-gray-200 flex items-start justify-between">
              <div className="min-w-0">
                <div className="font-medium text-sm text-black">{c.name}</div>
                {c.description && <div className="text-xs text-gray-500">{c.description}</div>}
                <div className="text-xs text-gray-400 mt-1 flex flex-wrap gap-1">
                  {c.fields.map(f => <span key={f.key} className="px-1.5 py-0.5 rounded bg-gray-100">{f.key}: {f.masked}</span>)}
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <Button type="button" variant="outline" size="sm" disabled={busy || !loaded} onClick={() => startEdit(c)} className="border-gray-300 text-gray-700 h-7 px-2 text-xs">编辑</Button>
                <button disabled={busy || !loaded} aria-label={`删除凭据 ${c.name}`} onClick={() => del(c.name)} className="p-1 text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      )}
      <ConfirmDialog />
      {leave.dialog}
    </>
  )
}
