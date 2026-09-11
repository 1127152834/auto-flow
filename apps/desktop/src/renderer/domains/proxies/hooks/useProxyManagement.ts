import { useCallback, useEffect, useRef, useState } from 'react'
import { notify } from '../../../shared/components/Toaster'
import {
  errorDetail,
  errorMessage,
  type ActionResult,
  type ConnectionView,
  type GroupDraft,
  type GroupPage,
  type GroupView,
  type ProxyApi,
  type ProxyFilters,
  type ProxyMetadataDraft,
  type ProxyPage,
  type ProxyReferences,
  type ProxyView,
} from '../api'

const emptyProxies: ProxyPage = { items: [], offset: 0, limit: 50, matched_count: 0 }
const emptyGroups: GroupPage = { items: [], offset: 0, limit: 100, matched_count: 0 }

function actionError(result: ActionResult): Error {
  const error = new Error(result.error?.message ?? '操作失败') as Error & { error?: ActionResult['error'] }
  if (result.error) error.error = result.error
  return error
}

async function waitForAction(result: ActionResult): Promise<void> {
  if (result.status === 'completed') return
  if (result.status === 'failed' || !result.operation_id) throw actionError(result)
  throw new Error('操作已受理，结果尚未确认，请稍后刷新')
}

export function useProxyManagement(api: ProxyApi) {
  const [connection, setConnection] = useState<ConnectionView | null>(null)
  const [proxies, setProxies] = useState<ProxyPage>(emptyProxies)
  const [groups, setGroups] = useState<GroupPage>(emptyGroups)
  const [groupCandidates, setGroupCandidates] = useState<ProxyView[]>([])
  const [filters, setFilters] = useState<ProxyFilters>({ limit: 50 })
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string>()
  const [syncing, setSyncing] = useState(false)
  const [checkingId, setCheckingId] = useState<string>()
  const [connectionBusy, setConnectionBusy] = useState(false)
  const [connectionError, setConnectionError] = useState<string>()
  const [selectedProxy, setSelectedProxy] = useState<ProxyView | null>(null)
  const [references, setReferences] = useState<ProxyReferences>()
  const [groupBusy, setGroupBusy] = useState(false)
  const [groupError, setGroupError] = useState<string>()
  const [groupRiskRequired, setGroupRiskRequired] = useState(false)
  const [detailBusy, setDetailBusy] = useState(false)
  const [copying, setCopying] = useState<string>()
  const [retryUntil, setRetryUntil] = useState(0)
  const [clock, setClock] = useState(() => Date.now())
  const filterRequest = useRef(0)
  const detailRequest = useRef(0)
  const selectedProxyId = useRef<string | null>(null)

  const rememberRetryAfter = useCallback((error: unknown) => {
    const seconds = errorDetail(error)?.retry_after_seconds
    if (seconds != null && seconds > 0) {
      setClock(Date.now())
      setRetryUntil(Date.now() + seconds * 1_000)
    }
  }, [])

  useEffect(() => {
    if (retryUntil <= Date.now()) return
    const timer = window.setInterval(() => {
      const now = Date.now()
      setClock(now)
      if (now >= retryUntil) window.clearInterval(timer)
    }, 250)
    return () => window.clearInterval(timer)
  }, [retryUntil])

  const retryAfterSeconds = Math.max(0, Math.ceil((retryUntil - clock) / 1_000))

  const loadBase = useCallback(async () => {
    setLoading(true)
    setLoadError(undefined)
    try {
      const [nextConnection, nextGroups] = await Promise.all([api.getConnection(), api.listGroups()])
      setConnection(nextConnection)
      setGroups(nextGroups)
      if (!nextConnection) {
        setProxies(emptyProxies)
        setGroupCandidates([])
      } else {
        setGroupCandidates(await api.listAllProxies())
      }
    } catch (error) {
      rememberRetryAfter(error)
      setLoadError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [api, rememberRetryAfter])

  useEffect(() => { void loadBase() }, [loadBase])

  useEffect(() => {
    if (!connection) return
    const request = ++filterRequest.current
    const timeout = window.setTimeout(() => {
      void api.listProxies(filters).then((page) => {
        if (request === filterRequest.current) setProxies(page)
      }).catch((error) => {
        if (request === filterRequest.current) {
          rememberRetryAfter(error)
          setLoadError(errorMessage(error))
        }
      })
    }, filters.q ? 200 : 0)
    return () => window.clearTimeout(timeout)
  }, [api, connection, filters, rememberRetryAfter])

  const reload = useCallback(async () => {
    await loadBase()
  }, [loadBase])

  const saveConnection = useCallback(async (name: string, apiKey: string) => {
    setConnectionBusy(true)
    setConnectionError(undefined)
    try {
      const keyChanged = !connection || Boolean(apiKey.trim())
      let next = connection
        ? keyChanged ? await api.replaceApiKey(connection, apiKey) : connection
        : await api.createConnection(name, apiKey)
      if (next.name !== name) next = await api.updateConnection(next, name)
      setConnection(next)
      if (keyChanged) {
        try {
          await waitForAction(await api.sync(next.id))
        } catch (error) {
          rememberRetryAfter(error)
          await loadBase()
          const message = `连接已保存，代理同步暂不可用：${errorMessage(error)}`
          setLoadError(message)
          notify({ title: '连接已保存，代理同步暂不可用', tone: 'info' })
          return
        }
      }
      await loadBase()
      notify({ title: keyChanged ? 'ProxyPanel 已连接并同步' : '连接名称已更新', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      setConnectionError(errorMessage(error))
      throw error
    } finally {
      setConnectionBusy(false)
    }
  }, [api, connection, loadBase, rememberRetryAfter])

  const disconnect = useCallback(async () => {
    if (!connection) return
    try {
      await api.disconnect(connection.id)
      setConnection(null)
      setProxies(emptyProxies)
      setGroupCandidates([])
      notify({ title: '已断开 ProxyPanel', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      setLoadError(errorMessage(error))
      notify({ title: errorMessage(error), tone: 'error' })
    }
  }, [api, connection, rememberRetryAfter])

  const sync = useCallback(async () => {
    if (!connection || syncing) return
    setSyncing(true)
    try {
      await waitForAction(await api.sync(connection.id))
      const [nextConnection, nextProxies, nextCandidates] = await Promise.all([api.getConnection(), api.listProxies(filters), api.listAllProxies()])
      setConnection(nextConnection)
      setProxies(nextProxies)
      setGroupCandidates(nextCandidates)
      notify({ title: '代理已同步', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      setLoadError(errorMessage(error))
      notify({ title: errorMessage(error), tone: 'error' })
    } finally {
      setSyncing(false)
    }
  }, [api, connection, filters, rememberRetryAfter, syncing])

  const probe = useCallback(async (proxy: ProxyView) => {
    if (checkingId) return
    const protocol = proxy.http_endpoint ? 'http' : proxy.socks5_endpoint ? 'socks5' : null
    if (!protocol) return
    setCheckingId(proxy.id)
    try {
      await waitForAction(await api.probeProxy(proxy.id, protocol))
      const refreshed = await api.getProxy(proxy.id)
      setProxies((current) => ({ ...current, items: current.items.map((item) => item.id === refreshed.id ? refreshed : item) }))
      setGroupCandidates((current) => current.map((item) => item.id === refreshed.id ? refreshed : item))
      if (selectedProxyId.current === refreshed.id) setSelectedProxy(refreshed)
      notify({ title: refreshed.health.state === 'healthy' ? '代理连接正常' : '代理检测完成', tone: refreshed.health.state === 'healthy' ? 'success' : 'info' })
    } catch (error) {
      rememberRetryAfter(error)
      notify({ title: errorMessage(error), tone: 'error' })
    } finally {
      setCheckingId(undefined)
    }
  }, [api, checkingId, rememberRetryAfter])

  const openProxy = useCallback((proxy: ProxyView) => {
    const request = ++detailRequest.current
    selectedProxyId.current = proxy.id
    setSelectedProxy(proxy)
    setReferences(undefined)
    void Promise.all([api.getProxy(proxy.id), api.getProxyReferences(proxy.id)])
      .then(([detail, nextReferences]) => {
        if (request !== detailRequest.current || selectedProxyId.current !== detail.id) return
        setSelectedProxy(detail)
        setReferences(nextReferences)
      })
      .catch((error) => {
        if (request !== detailRequest.current) return
        rememberRetryAfter(error)
        notify({ title: errorMessage(error), tone: 'error' })
      })
  }, [api, rememberRetryAfter])

  const closeProxy = useCallback(() => {
    detailRequest.current += 1
    selectedProxyId.current = null
    setSelectedProxy(null)
    setReferences(undefined)
  }, [])

  const updateProxy = useCallback(async (proxy: ProxyView, draft: ProxyMetadataDraft) => {
    setDetailBusy(true)
    try {
      const updated = await api.updateProxy(proxy, draft)
      setProxies((current) => ({ ...current, items: current.items.map((item) => item.id === updated.id ? updated : item) }))
      setGroupCandidates((current) => current.map((item) => item.id === updated.id ? updated : item))
      if (selectedProxyId.current === updated.id) setSelectedProxy(updated)
      notify({ title: '代理本地设置已保存', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      notify({ title: errorMessage(error), tone: 'error' })
    } finally {
      setDetailBusy(false)
    }
  }, [api, rememberRetryAfter])

  const copyCredentials = useCallback(async (proxy: ProxyView, protocol: 'http' | 'socks5', format: 'username' | 'password' | 'url') => {
    const copy = window.autoflow?.copyProxyCredentials
    if (!proxy.credential_available || !copy) return
    const key = `${protocol}:${format}`
    setCopying(key)
    try {
      await copy({ proxyId: proxy.id, protocol, format })
      notify({ title: '已复制到剪贴板', tone: 'success' })
    } catch (error) {
      notify({ title: errorMessage(error), tone: 'error' })
    } finally {
      setCopying(undefined)
    }
  }, [])

  const saveGroup = useCallback(async (group: GroupView | null, draft: GroupDraft, acknowledgeRisk: boolean) => {
    setGroupBusy(true)
    setGroupError(undefined)
    setGroupRiskRequired(false)
    try {
      const saved = group
        ? await api.updateGroup(group, draft, acknowledgeRisk)
        : await api.createGroup(draft, acknowledgeRisk)
      setGroups((current) => {
        const exists = current.items.some((item) => item.id === saved.id)
        const items = exists ? current.items.map((item) => item.id === saved.id ? saved : item) : [...current.items, saved]
        return { ...current, items, matched_count: current.matched_count + (exists ? 0 : 1) }
      })
      notify({ title: '本地代理组已保存', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      const detail = errorDetail(error)
      setGroupError(errorMessage(error))
      setGroupRiskRequired(detail?.code === 'PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED')
      throw error
    } finally {
      setGroupBusy(false)
    }
  }, [api, rememberRetryAfter])

  const deleteGroup = useCallback(async (group: GroupView) => {
    try {
      await api.deleteGroup(group.id)
      setGroups((current) => ({ ...current, items: current.items.filter((item) => item.id !== group.id), matched_count: Math.max(0, current.matched_count - 1) }))
      notify({ title: '本地代理组已删除', tone: 'success' })
    } catch (error) {
      rememberRetryAfter(error)
      if (errorDetail(error)?.code === 'PROXY_GROUP_IN_USE') {
        try {
          const references = await api.getGroupReferences(group.id)
          const names = (references.profiles ?? []).map((item) => item.name).join('、')
          setLoadError(names ? `无法删除“${group.name}”，以下浏览器配置仍在引用：${names}` : errorMessage(error))
        } catch {
          setLoadError(errorMessage(error))
        }
      }
      notify({ title: errorMessage(error), tone: 'error' })
    }
  }, [api, rememberRetryAfter])

  return {
    connection,
    proxies,
    groups,
    groupCandidates,
    filters,
    loading,
    loadError,
    syncing,
    checkingId,
    connectionBusy,
    connectionError,
    selectedProxy,
    references,
    groupBusy,
    groupError,
    groupRiskRequired,
    detailBusy,
    copying,
    retryAfterSeconds,
    canCopyCredentials: Boolean(window.autoflow?.copyProxyCredentials),
    setFilters,
    setConnectionError,
    setGroupError,
    reload,
    saveConnection,
    disconnect,
    sync,
    probe,
    openProxy,
    closeProxy,
    updateProxy,
    copyCredentials,
    saveGroup,
    deleteGroup,
  }
}
