import { useState, type FormEvent } from 'react'
import type { License } from '../../../shared/api/types'
import { Button } from '../../../shared/components/ui/button'
import { PasswordInput } from '../../../shared/components/ui/password-input'

export type LicensePanelProps = {
  status?: License | null
  busy: boolean
  disabled?: boolean
  error?: string | null
  onConnect(licenseKey: string): void | Promise<void>
  onDisconnect(): void | Promise<void>
}

export function LicensePanel({ status, busy, disabled = false, error, onConnect, onDisconnect }: LicensePanelProps) {
  const [licenseKey, setLicenseKey] = useState('')
  const licensed = status?.configured === true && status.valid

  async function submit(event: FormEvent) {
    event.preventDefault()
    const key = licenseKey.trim()
    if (disabled || !key) return
    try {
      await onConnect(key)
      setLicenseKey('')
    } catch { /* The parent renders the mutation error. */ }
  }

  async function signOut() {
    if (disabled) return
    try { await onDisconnect() }
    catch { /* The parent renders the mutation error. */ }
  }

  return <section aria-labelledby="kernel-license-title" className="rounded-card border border-line bg-surface-subtle p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 id="kernel-license-title" className="m-0 text-sm font-semibold text-ink">CloakBrowser License</h3>
        {licensed ? <p className="mb-0 mt-1 text-sm text-muted">
          {status.plan ?? '套餐未知'} · 到期时间 {status.expires ?? '未知'} · 会话数 {status.seats ? `${status.seats.active ?? '未知'} / ${status.seats.limit ?? '未知'}` : '未知'}
        </p> : <p className="mb-0 mt-1 text-sm text-muted">登录后可下载正式版内核。</p>}
      </div>
      {licensed ? <Button type="button" disabled={disabled || busy} onClick={() => void signOut()}>退出登录</Button> : null}
    </div>
    {!licensed ? <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={(event) => void submit(event)}>
      <label className="sr-only" htmlFor="cloakbrowser-license-key">License Key</label>
      <PasswordInput id="cloakbrowser-license-key" autoComplete="off" value={licenseKey} disabled={disabled || busy} placeholder="License Key" onChange={(event) => setLicenseKey(event.target.value)} />
      <Button type="submit" variant="primary" className="shrink-0 whitespace-nowrap" disabled={disabled || busy || !licenseKey.trim()}>{busy ? '正在验证…' : '验证并登录'}</Button>
    </form> : null}
    {status?.configured && !status.valid ? <p role="alert" className="mb-0 mt-3 text-sm text-danger">已保存的 License 当前无效，请重新登录。</p> : null}
    {error ? <p role="alert" className="mb-0 mt-3 text-sm text-danger">{error}</p> : null}
  </section>
}
