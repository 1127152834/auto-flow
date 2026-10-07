// Source: WebRPA@5ccb900e, lib/requiredFields.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 模块必填字段（来源：后端模块 schema），用于配置面板的必填校验提示。
 * 全局缓存一次，避免重复请求。
 */
import { useCallback, useMemo, useSyncExternalStore } from 'react'
import { apiRequest } from '../api'
import { getFieldLabel } from './fieldLabels'
import { getStudioTransportRevision } from '../api/transport'
import type { components } from '../../../shared/api/generated'

type RequiredFieldMetadata = components['schemas']['StudioModuleRequiredFields']
type ConditionalSpec = components['schemas']['StudioConditionalRequired']
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string' && !!value.trim()
const fields = (value: unknown): value is string[] => Array.isArray(value) && value.every(text) && new Set(value).size === value.length
export function isRequiredFieldMetadata(value: unknown): value is RequiredFieldMetadata {
  if (!record(value) || !text(value.schemaRevision) || !fields(value.coveredModules)
    || !record(value.requiredFields) || !record(value.conditionalRequired) || !record(value.fieldLabels)
    || Object.keys(value).some(key => !['schemaRevision','coveredModules','requiredFields','conditionalRequired','fieldLabels'].includes(key))) return false
  const covered = new Set(value.coveredModules)
  if ([value.requiredFields,value.conditionalRequired,value.fieldLabels].some(map => Object.keys(map).some(key => !covered.has(key)))) return false
  return Object.values(value.requiredFields).every(fields)
    && Object.values(value.fieldLabels).every(labels => record(labels) && Object.entries(labels).every(([key,label]) => text(key) && text(label)))
    && Object.values(value.conditionalRequired).every(cond => record(cond) && text(cond.field)
      && (cond.default === null || typeof cond.default === 'string') && record(cond.map)
      && Object.keys(cond).every(key => ['field','default','map'].includes(key))
      && Object.entries(cond.map).every(([key,list]) => text(key) && fields(list)))
}
let cache: { revision: number; data?: RequiredFieldMetadata; promise?: Promise<RequiredFieldMetadata> } | null = null
export function fetchRequiredFields(refresh = false): Promise<RequiredFieldMetadata> {
  const revision = getStudioTransportRevision()
  if (cache?.revision === revision) {
    if (cache.promise) return cache.promise
    if (!refresh && cache.data) return Promise.resolve(cache.data)
  }
  const entry: NonNullable<typeof cache> = { revision }
  cache = entry
  entry.promise = (async () => {
    const response = await apiRequest<RequiredFieldMetadata>('/system/module-required-fields', { signal: AbortSignal.timeout(10000) })
    if (revision !== getStudioTransportRevision()) throw new Error('服务连接已变化，已丢弃旧字段规则')
    if (!response.success) throw new Error(response.error || '必填字段规则加载失败')
    if (!isRequiredFieldMetadata(response.data)) throw new Error('必填字段规则响应格式错误')
    entry.data = response.data
    return response.data
  })().finally(() => { entry.promise = undefined; if (!entry.data && cache === entry) cache = null })
  return entry.promise
}

type RuleState = { data: RequiredFieldMetadata | null; loading: boolean; error: string | null }
const RULES_LOADING: RuleState = { data: null, loading: true, error: null }
let ruleState: RuleState = RULES_LOADING
let ruleRequest = 0
let detachRuleEvents: (() => void) | null = null
const ruleListeners = new Set<() => void>()

function setRuleState(next: RuleState) {
  if (next === ruleState) return
  ruleState = next
  for (const listener of ruleListeners) listener()
}

function loadRules(refresh = false) {
  const request = ++ruleRequest
  setRuleState(RULES_LOADING)
  void fetchRequiredFields(refresh).then(data => {
    if (request === ruleRequest) setRuleState({ data, loading: false, error: null })
  }).catch(error => {
    if (request === ruleRequest) setRuleState({ data: null, loading: false, error: error instanceof Error ? error.message : String(error) })
  })
}

// 所有使用方共用一份状态、一次读取、一组事件监听；最后一个使用方卸载时全部撤销。
function subscribeRules(listener: () => void) {
  ruleListeners.add(listener)
  if (ruleListeners.size === 1) {
    const replacement = () => loadRules()
    const reconnect = () => loadRules(true)
    window.addEventListener('studio:transport-changed', replacement)
    window.addEventListener('studio:connection-restored', reconnect)
    detachRuleEvents = () => {
      window.removeEventListener('studio:transport-changed', replacement)
      window.removeEventListener('studio:connection-restored', reconnect)
    }
    loadRules()
  }
  return () => {
    ruleListeners.delete(listener)
    if (ruleListeners.size === 0) {
      detachRuleEvents?.()
      detachRuleEvents = null
      ruleRequest++
      ruleState = RULES_LOADING
    }
  }
}

/** Share only successful metadata within one transport generation; failures remain visible and retryable. */
export function useRequiredFields() {
  const state = useSyncExternalStore(subscribeRules, () => ruleState, () => RULES_LOADING)
  const retry = useCallback(() => loadRules(true), [])
  return useMemo(() => ({ ...state, retry }), [state, retry])
}

/** 计算某模块当前缺失的必填字段（支持按模式的条件必填，如 real_keyboard 不同 inputType） */
export function getMissingRequired(
  moduleType: string,
  data: Record<string, unknown>,
  reqMap: Record<string, string[]>,
  conditions: Record<string, ConditionalSpec> = {},
): string[] {
  // 基础必填 + 条件必填（按判别字段当前取值）
  const base = Object.hasOwn(reqMap, moduleType) ? reqMap[moduleType] : []
  const req = [...base]
  const cond = Object.hasOwn(conditions, moduleType) ? conditions[moduleType] : undefined
  if (cond && cond.map && cond.field) {
    let val = data[cond.field] as string | null | undefined
    if (val === undefined || val === null || val === '') val = cond.default
    const extra = val && Object.hasOwn(cond.map, val) ? cond.map[val] : []
    for (const f of extra) if (!req.includes(f)) req.push(f)
  }
  if (req.length === 0) return []
  return req.filter((f) => {
    const v = data[f]
    if (v === undefined || v === null) return true
    if (typeof v === 'string') return v.trim() === ''
    if (Array.isArray(v)) return v.length === 0
    return false
  })
}

/** 计算缺失必填字段，并返回其中文标签（优先后端 desc，其次通用映射，最后字段名本身） */
export function getMissingRequiredLabels(
  moduleType: string,
  data: Record<string, unknown>,
  reqMap: Record<string, string[]>,
  metadata?: Pick<RequiredFieldMetadata, 'conditionalRequired' | 'fieldLabels'>,
): string[] {
  const missing = getMissingRequired(moduleType, data, reqMap, metadata?.conditionalRequired)
  const moduleLabels = metadata?.fieldLabels[moduleType]
  return missing.map((f) => getFieldLabel(f, moduleLabels))
}
