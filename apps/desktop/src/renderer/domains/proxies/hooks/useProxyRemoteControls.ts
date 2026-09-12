import { useCallback, useEffect, useRef, useState } from 'react'
import { notify } from '../../../shared/components/Toaster'
import { errorDetail, errorMessage, type ActionResult, type LocationList, type ProxyApi, type ProxyView, type RemoteOperation, type RemoteState, type RotationSchedule } from '../api'

export function useProxyRemoteControls(api: ProxyApi, proxy: ProxyView, onChanged: () => Promise<void>) {
  const [remote, setRemote] = useState<RemoteState>()
  const [schedule, setSchedule] = useState<RotationSchedule>()
  const [operation, setOperation] = useState<RemoteOperation>()
  const [locations, setLocations] = useState<LocationList>()
  const [error, setError] = useState<string>()
  const [operationError, setOperationError] = useState<string>()
  const [scheduleError, setScheduleError] = useState<string>()
  const [locationError, setLocationError] = useState<string>()
  const [pollGeneration, setPollGeneration] = useState(0)
  const [loading, setLoading] = useState(true)
  const [locationsLoading, setLocationsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [retryUntil, setRetryUntil] = useState(0)
  const [clock, setClock] = useState(Date.now())
  const epoch = useRef(0)
  const inFlight = useRef(false)
  const changed = useRef(onChanged)
  changed.current = onChanged
  const revision = useRef(proxy.revision)
  revision.current = proxy.revision
  const seen = useRef(new Set<string>())
  const retrySeconds = Math.max(0, Math.ceil((retryUntil - clock) / 1000))
  const cooldown = useCallback((value: unknown) => {
    const seconds = errorDetail(value)?.retry_after_seconds
    if (seconds && seconds > 0) { setRetryUntil(Date.now() + seconds * 1000); setClock(Date.now()) }
  }, [])
  useEffect(() => {
    if (!retrySeconds) return
    const timer = setInterval(() => setClock(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [retrySeconds])

  const refresh = useCallback(async () => {
    const token = epoch.current
    setLoading(true)
    setPollGeneration(value => value + 1)
    await Promise.all([
      api.getLatestOperation(proxy.id).then(async value => {
        if (token !== epoch.current) return
        setOperation(value ?? undefined); setOperationError(undefined)
        if (value?.status === 'succeeded' && value.resource_revision != null && value.resource_revision > revision.current) await changed.current()
      }).catch(e => { if (token === epoch.current) setOperationError(errorMessage(e)) }),
      api.getRemoteState(proxy.id).then(value => {
        if (token !== epoch.current) return
        setRemote(value); setError(undefined)
      }).catch(e => { if (token === epoch.current) { cooldown(e); setError(errorMessage(e)) } }),
      api.getRotation(proxy.id).then(value => {
        if (token !== epoch.current) return
        setSchedule(value); setScheduleError(undefined)
      }).catch(e => { if (token === epoch.current) { cooldown(e); setScheduleError(errorMessage(e)) } }),
    ])
    if (token === epoch.current) setLoading(false)
  }, [api, proxy.id, cooldown])

  useEffect(() => {
    ++epoch.current
    void refresh()
    return () => { ++epoch.current }
  }, [refresh])

  const settled = useCallback(async (value: RemoteOperation) => {
    const token = epoch.current
    setOperation(value)
    if (value.status === 'queued' || value.status === 'running' || seen.current.has(value.id + value.status)) return
    seen.current.add(value.id + value.status)
    if (value.status === 'succeeded') {
      notify({title: '远程操作已确认完成', tone: 'success'})
      try { await changed.current(); if (token === epoch.current) await refresh() } catch { if (token === epoch.current) setError('操作已确认完成，但本地列表刷新失败，请重新加载') }
    } else if (value.status === 'failed') {
      const message = value.error?.message || '操作被拒绝'
      setError(message); notify({title: message, tone: 'error'})
      if (value.error?.retry_after_seconds) { setRetryUntil(Date.now() + value.error.retry_after_seconds * 1000); setClock(Date.now()) }
    }
  }, [refresh])

  const operationId = operation?.id
  const operationStatus = operation?.status
  useEffect(() => {
    if (!operationId || !operationStatus || !['queued', 'running'].includes(operationStatus)) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    let failures = 0
    const poll = async () => {
      if (cancelled) return
      if (document.visibilityState === 'hidden') { timer = setTimeout(() => void poll(), 2000); return }
      try {
        const value = await api.getOperation(operationId)
        if (cancelled) return
        failures = 0
        await settled(value)
        if (value.status !== 'running' && value.status !== 'queued') return
      } catch (e) {
        if (cancelled) return
        setError(errorMessage(e)); failures++
        if (failures >= 3) return
      }
      if (!cancelled) timer = setTimeout(() => void poll(), 2000)
    }
    timer = setTimeout(() => void poll(), 1000)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [api, operationId, operationStatus, pollGeneration, settled])

  const submit = async (command: () => Promise<ActionResult>): Promise<boolean> => {
    if (inFlight.current || retrySeconds || operation && ['queued', 'running', 'unknown'].includes(operation.status)) return false
    const token = epoch.current
    inFlight.current = true; setSubmitting(true); setError(undefined)
    try {
      const result = await command()
      if (token !== epoch.current) return false
      if (result.operation_id) {
        const value = await api.getOperation(result.operation_id)
        if (token !== epoch.current) return false
        await settled(value)
      }
      else if (result.status === 'failed') throw new Error(result.error?.message ?? '操作失败')
      else await refresh()
      return true
    } catch (e) {
      if (token === epoch.current) {
        cooldown(e); await refresh(); if (token === epoch.current) setError(errorMessage(e))
        // Recover the recorded operation after a lost acceptance response;
        // never resend a write automatically.
      }
      return false
    } finally {
      inFlight.current = false
      if (token === epoch.current) setSubmitting(false)
    }
  }

  const loadLocations = async () => {
    const token = epoch.current
    setLocationsLoading(true); setLocationError(undefined)
    try { const result = await api.getLocations(proxy.connection_id); if (token === epoch.current) setLocations(result) }
    catch (e) { if (token === epoch.current) { cooldown(e); setLocationError(errorMessage(e)) } }
    finally { if (token === epoch.current) setLocationsLoading(false) }
  }
  const reconcile = async () => {
    if (!operation || submitting) return
    const token = epoch.current
    setSubmitting(true)
    try { const value = await api.reconcileOperation(operation.id); if (token === epoch.current) { setOperation(value); setError(undefined) } }
    catch (e) { if (token === epoch.current) { setError(errorMessage(e)); cooldown(e) } }
    finally { if (token === epoch.current) setSubmitting(false) }
  }
  const acknowledge = async () => {
    if (!operation || submitting) return
    const token = epoch.current
    setSubmitting(true)
    try { const value = await api.acknowledgeOperation(operation.id); if (token === epoch.current) { setOperation(value); setError(undefined) } }
    catch (e) { if (token === epoch.current) setError(errorMessage(e)) }
    finally { if (token === epoch.current) setSubmitting(false) }
  }
  return {remote, schedule, operation, locations, error: error || operationError, scheduleError, locationError, loading, locationsLoading, submitting,
    busy: submitting || Boolean(operation && ['queued', 'running', 'unknown'].includes(operation.status)),
    retrySeconds, refresh, submit, loadLocations, reconcile, acknowledge}
}
