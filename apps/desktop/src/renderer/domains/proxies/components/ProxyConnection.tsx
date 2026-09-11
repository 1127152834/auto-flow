import { useEffect, useState, type FormEvent } from 'react'
import { ArrowsClockwise, GearSix, PlugsConnected } from '@phosphor-icons/react'
import type { ConnectionView } from '../api'
import { formatTime, StatusPill } from './presentation'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../../shared/components/ui/alert-dialog'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../../shared/components/ui/dialog'

type ConnectionCardProps = {
  connection: ConnectionView | null
  syncing: boolean
  onConfigure: () => void
  onSync: () => void
  onDisconnect: () => Promise<void>
}

export function ConnectionCard({ connection, syncing, onConfigure, onSync, onDisconnect }: ConnectionCardProps) {
  if (!connection) {
    return (
      <section className="flex flex-col gap-5 rounded-card border border-line bg-surface p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-card bg-clay-soft text-clay"><PlugsConnected size={24} /></span>
          <div>
            <h2 className="text-base font-semibold text-ink">连接 ProxyPanel</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">连接后同步专用移动代理。API Key 会保存到系统凭据库。</p>
          </div>
        </div>
        <Button variant="primary" onClick={onConfigure}>连接 ProxyPanel</Button>
      </section>
    )
  }

  const status = connection.status === 'connected'
    ? { label: '已连接', tone: 'success' as const }
    : connection.status === 'verifying'
      ? { label: '验证中', tone: 'neutral' as const }
      : { label: '连接失败', tone: 'danger' as const }

  return (
    <section className="rounded-card border border-line bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-card bg-clay-soft text-clay"><PlugsConnected size={24} /></span>
          <div className="grid gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold text-ink">{connection.name}</h2>
              <StatusPill tone={status.tone}>{status.label}</StatusPill>
            </div>
            <p className="text-sm text-muted">最近同步：{formatTime(connection.last_synced_at)}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={onSync} disabled={syncing || connection.status !== 'connected'}>
            <ArrowsClockwise className={syncing ? 'animate-spin' : ''} />{syncing ? '同步中…' : '刷新代理'}
          </Button>
          <Button variant="primary" onClick={onConfigure}><GearSix />连接设置</Button>
          <AlertDialog>
            <AlertDialogTrigger asChild><Button variant="ghost">断开</Button></AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogTitle>断开 ProxyPanel？</AlertDialogTitle>
              <AlertDialogDescription>这只会清除本地连接和可清理的投影，不会删除远程代理。存在引用时系统会阻止操作。</AlertDialogDescription>
              <div className="flex justify-end gap-2">
                <AlertDialogCancel asChild><Button>取消</Button></AlertDialogCancel>
                <AlertDialogAction asChild><Button variant="primary" onClick={() => void onDisconnect()}>确认断开</Button></AlertDialogAction>
              </div>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
      {connection.last_error ? <p className="mt-4 rounded-control bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{connection.last_error.message}</p> : null}
    </section>
  )
}

type ConnectionDialogProps = {
  open: boolean
  connection: ConnectionView | null
  busy: boolean
  error?: string
  onOpenChange: (open: boolean) => void
  onSubmit: (name: string, apiKey: string) => Promise<void>
}

export function ConnectionDialog({ open, connection, busy, error, onOpenChange, onSubmit }: ConnectionDialogProps) {
  const [name, setName] = useState('ProxyPanel')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    if (open) setName(connection?.name ?? 'ProxyPanel')
    if (!open) {
      setApiKey('')
      setShowKey(false)
    }
  }, [connection?.name, open])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || (!connection && !apiKey.trim())) return
    try {
      await onSubmit(name.trim(), apiKey)
    } catch {
      // The caller owns the structured error state; the form only clears the secret.
    } finally {
      setApiKey('')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} busy={busy}>
      <DialogContent aria-describedby="proxy-connection-description">
        <DialogTitle>{connection ? '更新 ProxyPanel 连接' : '连接 ProxyPanel'}</DialogTitle>
        <DialogDescription id="proxy-connection-description">Key 只在本次提交期间保留，不会在页面中回显。</DialogDescription>
        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <FormField label="连接名称" htmlFor="proxy-connection-name">
            <Input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} autoComplete="off" />
          </FormField>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-ink" htmlFor="proxy-api-key">API Key</label>
            <div className="flex gap-2">
              <Input id="proxy-api-key" type={showKey ? 'text' : 'password'} value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" spellCheck={false} aria-invalid={error ? true : undefined} aria-describedby={error ? 'proxy-api-key-error' : connection?.has_secret ? 'proxy-api-key-hint' : undefined} />
              <Button type="button" onClick={() => setShowKey((value) => !value)}>{showKey ? '隐藏' : '显示'}</Button>
            </div>
            {connection?.has_secret && !error ? <p className="text-xs text-muted" id="proxy-api-key-hint">已保存现有 Key；输入新 Key 后会先验证再替换。</p> : null}
            {error ? <p className="text-xs text-clay" id="proxy-api-key-error" role="alert">{error}</p> : null}
          </div>
          <div className="flex justify-end gap-2">
            <DialogClose asChild><Button type="button">取消</Button></DialogClose>
            <Button type="submit" variant="primary" disabled={busy || !name.trim() || (!connection && !apiKey.trim())}>{busy ? '正在保存…' : connection ? apiKey.trim() ? '验证并保存' : '保存名称' : '验证并连接'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
