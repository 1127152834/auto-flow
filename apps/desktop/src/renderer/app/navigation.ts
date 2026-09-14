import { useCallback, useEffect, useRef, useState } from 'react'
import type { DataTableTab } from '../domains/project-data/types'
import type { ProjectRoute, ProjectTab } from '../domains/projects/types'
import { decodeRecordKey, encodeRecordKey } from '../domains/project-data/record-route'

export type AppRoute = 'dashboard' | 'projects' | 'profiles' | 'proxies' | 'models' | 'settings'
const globalRoutes: AppRoute[] = ['dashboard', 'projects', 'profiles', 'proxies', 'models', 'settings']
const projectTabs: ProjectTab[] = ['overview', 'automations', 'runs', 'statistics', 'data', 'environments']
const projectIdPattern = /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i
const recordKeyTypes = ['text', 'integer', 'uuid'] as const

export function parseAppLocation(hash: string): { section: AppRoute; project?: ProjectRoute; error?: string } {
  const parts = hash.replace(/^#\/?/, '').split('?')[0].split('/')
  if (parts[0] !== 'projects') return { section: globalRoutes.includes(parts[0] as AppRoute) ? parts[0] as AppRoute : 'dashboard' }
  if (parts.length === 1) return { section: 'projects', project: { tab: 'overview' } }
  if (parts.length === 4 && projectIdPattern.test(parts[1]) && parts[2] === 'automations' && (parts[3] === 'new' || projectIdPattern.test(parts[3]))) {
    return { section: 'projects', project: { projectId: parts[1], tab: 'automations', ...(parts[3] === 'new' ? { automationCreate: true } : { automationId: parts[3] }) } }
  }
  if (parts.length === 6 && projectIdPattern.test(parts[1]) && parts[2] === 'data' && projectIdPattern.test(parts[3]) && parts[4] === 'records' && parts[5] === 'new') {
    return { section: 'projects', project: { projectId: parts[1], tab: 'data', tableId: parts[3], dataTab: 'records', record: { mode: 'create' } } }
  }
  if ((parts.length === 8 || parts.length === 9) && projectIdPattern.test(parts[1]) && parts[2] === 'data' && projectIdPattern.test(parts[3]) && parts[4] === 'records' && projectIdPattern.test(parts[5]) && recordKeyTypes.includes(parts[6] as typeof recordKeyTypes[number]) && (parts.length === 8 || parts[8] === 'edit')) {
    try {
      const recordKey = decodeRecordKey(parts[6] as typeof recordKeyTypes[number], parts[7])
      return { section: 'projects', project: { projectId: parts[1], tab: 'data', tableId: parts[3], dataTab: 'records', record: { mode: parts.length === 9 ? 'edit' : 'detail', datasetGeneration: parts[5], recordKey } } }
    } catch { return { section: 'projects', error: '项目地址无效，请从项目目录重新打开。' } }
  }
  if (parts.length === 5 && projectIdPattern.test(parts[1]) && parts[2] === 'data' && projectIdPattern.test(parts[3]) && ['records', 'fields', 'statuses', 'source', 'settings'].includes(parts[4])) {
    return { section: 'projects', project: { projectId: parts[1], tab: 'data', tableId: parts[3], dataTab: parts[4] as DataTableTab } }
  }
  if (parts.length !== 3 || !projectIdPattern.test(parts[1]) || !projectTabs.includes(parts[2] as ProjectTab)) {
    return { section: 'projects', error: '项目地址无效，请从项目目录重新打开。' }
  }
  return { section: 'projects', project: { projectId: parts[1], tab: parts[2] as ProjectTab } }
}

export function projectHash(route: ProjectRoute) {
  if (!route.projectId) return '#/projects'
  const base = `#/projects/${encodeURIComponent(route.projectId)}/${route.tab}`
  if (route.automationCreate || route.automationId) {
    if (route.tab !== 'automations' || (route.automationCreate && route.automationId) || (route.automationId && !projectIdPattern.test(route.automationId))) throw new Error('自动化地址无效')
    return `${base}/${route.automationCreate ? 'new' : route.automationId}`
  }
  if (route.record) {
    if (route.tab !== 'data' || !route.tableId || (route.dataTab ?? 'records') !== 'records') throw new Error('记录路由只能位于数据表记录页')
    const records = `${base}/${encodeURIComponent(route.tableId)}/records`
    if (route.record.mode === 'create') return `${records}/new`
    if (!projectIdPattern.test(route.record.datasetGeneration)) throw new Error('数据代次无效')
    const identity = `${records}/${route.record.datasetGeneration}/${route.record.recordKey.type}/${encodeRecordKey(route.record.recordKey)}`
    return route.record.mode === 'edit' ? `${identity}/edit` : identity
  }
  return route.tab === 'data' && route.tableId ? `${base}/${encodeURIComponent(route.tableId)}/${route.dataTab ?? 'records'}` : base
}

type Entry = { hash: string; index: number }
type LeaveGuard = (() => Promise<boolean>) | null
const historyIndex = () => typeof window.history.state?.afNavigationIndex === 'number' ? window.history.state.afNavigationIndex as number : null
const writeHistory = (mode: 'pushState' | 'replaceState', entry: Entry) => window.history[mode]({ ...window.history.state, afNavigationIndex: entry.index }, '', entry.hash)

/** The app is the only hash owner. Restore the history cursor before asking to leave. */
export function useGuardedHashNavigation() {
  const [hash, setHash] = useState(() => window.location.hash || '#/dashboard')
  const current = useRef<Entry>({ hash, index: historyIndex() ?? 0 })
  const guard = useRef<LeaveGuard>(null)
  const busy = useRef(false)
  const epoch = useRef(0)
  const traversal = useRef<{ entry: Entry; done: () => void } | null>(null)
  const restoredHistory = useRef<Promise<void>>(Promise.resolve())
  const registerLeaveGuard = useCallback((next: LeaveGuard) => { guard.current = next }, [])
  const commit = useCallback((entry: Entry) => { current.current = entry; setHash(entry.hash) }, [])
  const allowed = useCallback(async () => { try { return await guard.current?.() ?? true } catch { return false } }, [])

  const navigate = useCallback(async (next: string) => {
    if (busy.current || next === current.current.hash) return
    busy.current = true
    const ticket = epoch.current
    try {
      const mayLeave = await allowed()
      await restoredHistory.current
      if (!mayLeave || ticket !== epoch.current) return
      const entry = { hash: next, index: current.current.index + 1 }
      writeHistory('pushState', entry); commit(entry)
    } finally { busy.current = false }
  }, [allowed, commit])

  const replace = useCallback((next: string, options: { preserveGuard?: boolean } = {}) => {
    epoch.current++
    if (!options.preserveGuard) guard.current = null
    const entry = { ...current.current, hash: next }
    writeHistory('replaceState', entry); commit(entry)
  }, [commit])

  useEffect(() => {
    writeHistory('replaceState', current.current)
    const move = (entry: Entry) => new Promise<void>(resolve => {
      if (historyIndex() === entry.index && window.location.hash === entry.hash) { resolve(); return }
      traversal.current = { entry, done: resolve }
      window.history.go(entry.index - (historyIndex() ?? current.current.index))
    })
    const changed = async () => {
      const storedIndex = historyIndex()
      const actual = { hash: window.location.hash || '#/dashboard', index: storedIndex ?? current.current.index + 1 }
      const traveling = traversal.current
      if (traveling) {
        if (actual.index === traveling.entry.index && actual.hash === traveling.entry.hash) {
          traversal.current = null; traveling.done()
        }
        return
      }
      if (actual.hash === current.current.hash) return
      // Direct hash navigation creates an entry without our index (some hosts inherit it).
      if (storedIndex === null || actual.index === current.current.index) {
        actual.index = current.current.index + 1; writeHistory('replaceState', actual)
      }
      if (busy.current) { restoredHistory.current = move(current.current); await restoredHistory.current; return }
      if (!guard.current) { commit(actual); return }
      busy.current = true
      const ticket = epoch.current
      try {
        await move(current.current)
        const mayLeave = await allowed()
        await restoredHistory.current
        if (!mayLeave || ticket !== epoch.current) return
        await move(actual)
        if (ticket === epoch.current) commit(actual)
      } finally { busy.current = false }
    }
    window.addEventListener('popstate', changed)
    window.addEventListener('hashchange', changed)
    return () => {
      epoch.current++
      window.removeEventListener('popstate', changed)
      window.removeEventListener('hashchange', changed)
      traversal.current?.done(); traversal.current = null
    }
  }, [allowed, commit])
  return { hash, navigate, replace, registerLeaveGuard }
}
