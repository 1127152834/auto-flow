import { useMemo, useState } from 'react'
import type { ApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Toaster } from '../../../shared/components/Toaster'
import { createProxyApi, type GroupView } from '../api'
import { useProxyManagement } from '../hooks/useProxyManagement'
import { ConnectionCard, ConnectionDialog } from '../components/ProxyConnection'
import { ProxySummary, ProxyTable } from '../components/ProxyFleet'
import { ProxyDetailDrawer } from '../components/ProxyDetailDrawer'
import { LocalProxyGroupEditor, LocalProxyGroupTable } from '../components/LocalProxyGroups'

export function ProxyManagementPage({ api }: { api: ApiClient }) {
  const proxyApi = useMemo(() => createProxyApi(api), [api])
  const state = useProxyManagement(proxyApi)
  const [connectionOpen, setConnectionOpen] = useState(false)
  const [groupOpen, setGroupOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<GroupView | null>(null)

  function openGroup(group: GroupView | null) {
    state.setGroupError(undefined)
    setEditingGroup(group)
    setGroupOpen(true)
  }

  return (
    <main className="min-h-dvh bg-canvas px-4 py-6 text-ink sm:px-6 lg:px-8">
      <div className="mx-auto grid w-full max-w-[1480px] gap-5">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">代理管理</h1>
          <p className="mt-1 text-sm text-muted">管理 ProxyPanel 移动代理，并为浏览器配置维护 AutoFlow 本地代理组。</p>
        </header>

        <ConnectionCard
          connection={state.connection}
          syncing={state.syncing}
          onConfigure={() => { state.setConnectionError(undefined); setConnectionOpen(true) }}
          onSync={() => void state.sync()}
          onDisconnect={state.disconnect}
        />

        {state.loading ? <ProxyPageSkeleton /> : null}

        {!state.loading && state.loadError ? (
          <div className="flex flex-col gap-3 rounded-control border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between" role="alert">
            <span>{state.loadError}。已加载的数据会继续保留。</span>
            <Button className="shrink-0" onClick={() => void state.reload()}>重新加载</Button>
          </div>
        ) : null}

        {!state.loading && state.connection ? (
          <>
            <ProxySummary page={state.proxies} />
            <ProxyTable
              page={state.proxies}
              filters={state.filters}
              checkingId={state.checkingId}
              onFiltersChange={state.setFilters}
              onOpen={state.openProxy}
              onProbe={(proxy) => void state.probe(proxy)}
            />
            <LocalProxyGroupTable page={state.groups} proxies={state.groupCandidates} onCreate={() => openGroup(null)} onEdit={openGroup} onDelete={state.deleteGroup} />
          </>
        ) : null}
      </div>

      <ConnectionDialog
        open={connectionOpen}
        connection={state.connection}
        busy={state.connectionBusy}
        error={state.connectionError}
        onOpenChange={setConnectionOpen}
        onSubmit={async (name, apiKey) => {
          await state.saveConnection(name, apiKey)
          setConnectionOpen(false)
        }}
      />

      <ProxyDetailDrawer
        open={Boolean(state.selectedProxy)}
        proxy={state.selectedProxy}
        references={state.references}
        probing={state.checkingId === state.selectedProxy?.id}
        onOpenChange={(open) => { if (!open) state.setSelectedProxy(null) }}
        onProbe={(proxy) => void state.probe(proxy)}
      />

      <LocalProxyGroupEditor
        open={groupOpen}
        group={editingGroup}
        proxies={state.groupCandidates}
        busy={state.groupBusy}
        error={state.groupError}
        riskRequired={state.groupRiskRequired}
        onOpenChange={setGroupOpen}
        onSubmit={async (draft, acknowledgeRisk) => {
          await state.saveGroup(editingGroup, draft, acknowledgeRisk)
          setGroupOpen(false)
        }}
      />
      <Toaster />
    </main>
  )
}

function ProxyPageSkeleton() {
  return <div className="grid animate-pulse gap-4" role="status" aria-label="正在加载代理管理"><div className="grid gap-3 sm:grid-cols-3">{[1, 2, 3].map((item) => <div className="h-28 rounded-card bg-surface-subtle" key={item} />)}</div><div className="h-72 rounded-card bg-surface-subtle" /><span className="sr-only">正在加载…</span></div>
}
