import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { AndroidManagementApi } from '../management-api'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'

type Props = {
  api: Pick<AndroidManagementApi, 'operations'>
  id: string
  deviceId: string
  deviceName: string
  instanceId: string
  onVerify?(operationId: string, requestId: string): void
  onClose(): void
}

export function OperationHistory({ api, id, deviceId, deviceName, instanceId, onVerify, onClose }: Props) {
  const [cursor, setCursor] = useState('')
  const [previous, setPrevious] = useState<string[]>([])
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [deviceId])
  const page = useQuery({
    queryKey: ['android-management', instanceId, 'operations', deviceId, cursor],
    queryFn: () => api.operations(`?deviceId=${encodeURIComponent(deviceId)}&limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
    refetchInterval: 3000,
  })
  const mismatched = page.data?.items.some(operation => operation.targetId !== deviceId) ?? false
  return <section id={id} aria-label={`${deviceName}操作历史`} className="rounded-card border border-line bg-surface p-5">
    <header className="flex items-center justify-between gap-3"><div><h3 ref={heading} tabIndex={-1} className="font-semibold">{deviceName} · 操作历史</h3><p className="mt-1 text-sm text-muted">按时间倒序，显示持久操作及其核实状态</p></div><button type="button" onClick={onClose}>关闭历史</button></header>
    {page.isPending && <p role="status">正在读取操作历史…</p>}
    {page.isError && <p role="alert">操作历史暂不可用，请重试。</p>}
    {mismatched && <p role="alert">操作历史与设备不匹配，请刷新后重试。</p>}
    {page.data && !mismatched && <>
      <TableScroll label={`${deviceName}操作记录表`}><Table><TableHeader><TableRow><TableHead>操作</TableHead><TableHead>状态</TableHead><TableHead>阶段</TableHead><TableHead>提交时间</TableHead><TableHead>处理</TableHead></TableRow></TableHeader><TableBody>
        {page.data.items.map(operation => <TableRow key={operation.operationId}>
          <TableCell>{operation.action}</TableCell><TableCell>{operation.state}</TableCell><TableCell>{operation.stageLabel}{operation.message && <p className="text-xs text-muted">{operation.message}</p>}</TableCell><TableCell>{new Date(operation.createdAt).toLocaleString()}</TableCell>
          <TableCell>{operation.state === 'needs_verification' && operation.allowedActions?.includes('verify') && onVerify && <button type="button" aria-label={`核实操作 ${operation.operationId}`} disabled={page.isError || page.isFetching} onClick={() => onVerify(operation.operationId, operation.requestId)}>核实状态</button>}</TableCell>
        </TableRow>)}
      </TableBody></Table></TableScroll>
      {!page.data.items.length && <p>此设备尚无管理操作。</p>}
      <div className="mt-3 flex items-center gap-3"><button type="button" aria-label="上一页操作历史" disabled={page.isError || page.isFetching || !previous.length} onClick={() => { setCursor(previous[previous.length - 1]); setPrevious(previous.slice(0, -1)) }}>上一页</button><span>第 {previous.length + 1} 页 · 共 {page.data.total} 项</span><button type="button" aria-label="下一页操作历史" disabled={page.isError || page.isFetching || !page.data.nextCursor} onClick={() => { setPrevious([...previous, cursor]); setCursor(page.data.nextCursor ?? '') }}>下一页</button></div>
    </>}
  </section>
}
