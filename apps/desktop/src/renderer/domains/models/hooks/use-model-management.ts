import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import type { ModelApi } from '../api'
import { refreshAfterModelConflict } from '../cache'
import { modelKeys, type AiModel, type ModelProvider } from '../model'
import type { ModelFeedback } from '../components/FeedbackCard'

export function useModelManagement(api: ModelApi, instanceId: string) {
  const cache = useQueryClient()
  const providers = useQuery({ queryKey: modelKeys.providers(instanceId), queryFn: api.listProviders, retry: false, refetchOnWindowFocus: false })
  const [selectedId, setSelectedId] = useState('')
  const [providerFeedback, setProviderFeedback] = useState<Record<string, ModelFeedback>>({})
  const [modelFeedback, setModelFeedback] = useState<ModelFeedback>()
  const [activity, setActivity] = useState<{ kind: 'crud' | 'provider' | 'model'; providerId: string; modelKey?: string }>()
  const lock = useRef(false)
  const viewEpoch = useRef(0)
  const selected = providers.data?.items.find(item => item.id === selectedId) ?? providers.data?.items[0]
  useEffect(() => { viewEpoch.current++; setModelFeedback(undefined) }, [selected?.id])
  const refresh = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: modelKeys.providers(instanceId) }),
      cache.invalidateQueries({ queryKey: modelKeys.options(instanceId) }),
    ])
  }
  const select = (id: string) => { viewEpoch.current++; setSelectedId(id); setModelFeedback(undefined) }
  const run = async (kind: 'crud' | 'provider' | 'model', provider: ModelProvider, operation: () => Promise<void>, modelKey?: string) => {
    if (lock.current) return
    lock.current = true
    setActivity({ kind, providerId: provider.id, modelKey })
    try { await operation() } finally { lock.current = false; setActivity(undefined) }
  }
  const testProvider = (provider: ModelProvider) => run('provider', provider, async () => {
    let feedback: ModelFeedback
    try {
      const result = await api.testProvider(provider.id)
      feedback = { tone: 'success', title: '供应商连接正常', detail: `${result.message} · ${Math.round(result.latencyMs)} ms` }
    } catch (error) {
      feedback = { tone: 'danger', title: '供应商连接失败', detail: errorMessage(error) }
    }
    setProviderFeedback(current => ({ ...current, [provider.id]: feedback }))
    await refresh()
  })
  const testModel = (provider: ModelProvider, model: AiModel) => run('model', provider, async () => {
    const epoch = viewEpoch.current
    setModelFeedback(undefined)
    let feedback: ModelFeedback
    try {
      const result = await api.testModel(provider.id, { modelKey: model.modelKey })
      feedback = { tone: 'success', title: `${result.modelKey} 调用成功`, detail: `${Math.round(result.latencyMs)} ms · ${result.outputPreview || '供应商已返回结果'}` }
    } catch (error) { refreshAfterModelConflict(cache, instanceId, error); feedback = { tone: 'danger', title: '模型调用失败', detail: errorMessage(error) } }
    if (viewEpoch.current === epoch) setModelFeedback(feedback)
  }, model.modelKey)
  const toggleProvider = (provider: ModelProvider) => run('crud', provider, async () => {
    try { await api.updateProvider(provider.id, { name: provider.name, description: provider.description, enabled: !provider.enabled }); await refresh() }
    catch (error) { refreshAfterModelConflict(cache, instanceId, error); setProviderFeedback(current => ({ ...current, [provider.id]: { tone: 'danger', title: '供应商更新失败', detail: errorMessage(error) } })) }
  })
  const toggleModel = (provider: ModelProvider, model: AiModel) => run('crud', provider, async () => {
    const epoch = viewEpoch.current
    setModelFeedback(undefined)
    try {
      await api.updateModel(model.id, { modelKey: model.modelKey, displayName: model.displayName, contextWindow: model.contextWindow, tagsJson: model.tagsJson, description: model.description, enabled: !model.enabled })
      await refresh()
    } catch (error) { refreshAfterModelConflict(cache, instanceId, error); if (viewEpoch.current === epoch) setModelFeedback({ tone: 'danger', title: '模型更新失败', detail: errorMessage(error) }) }
  })
  const removed = async (providerId: string) => {
    await cache.cancelQueries({ queryKey: modelKeys.discovery(instanceId, providerId) })
    cache.removeQueries({ queryKey: modelKeys.discovery(instanceId, providerId) })
    viewEpoch.current++
    setModelFeedback(undefined)
    await refresh()
  }
  const resetDiscovery = async (providerId: string) => {
    const queryKey = modelKeys.discovery(instanceId, providerId)
    await cache.cancelQueries({ queryKey, exact: true })
    cache.removeQueries({ queryKey, exact: true })
  }
  const providerSaved = (provider: ModelProvider) => {
    setProviderFeedback(current => { const next = { ...current }; delete next[provider.id]; return next })
    select(provider.id)
    void refresh()
  }
  return { providers, selected, select, refresh, removed, resetDiscovery, providerSaved, activity, providerFeedback, modelFeedback, testProvider, testModel, toggleProvider, toggleModel,
    clearModelFeedback: () => { viewEpoch.current++; setModelFeedback(undefined) } }
}

function errorMessage(error: unknown) { return error instanceof Error ? error.message : '操作未完成，请重试' }
