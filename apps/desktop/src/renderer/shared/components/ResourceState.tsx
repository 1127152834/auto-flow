import type { ReactNode } from 'react'
import { Button } from './ui/button'

type ResourceStateProps = { loading?: boolean; error?: string; empty?: boolean; retry?: () => void; children: ReactNode }

export function ResourceState({ loading = false, error, empty = false, retry, children }: ResourceStateProps) {
  if (loading) return <section className="grid gap-2 p-6 text-sm text-muted" role="status" aria-live="polite"><p>加载中…</p></section>
  if (error) return <section className="grid gap-3 p-6" role="alert"><p className="text-sm text-clay">{error}</p>{retry ? <Button onClick={retry}>重试</Button> : null}</section>
  if (empty) return <section className="grid gap-2 p-6 text-sm text-muted" role="status"><p>暂无数据</p></section>
  return <>{children}</>
}
