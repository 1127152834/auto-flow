// Source: WebRPA@5ccb900e, components/workflow/VariableTrackingPanel.tsx; see SOURCE.md for license and adaptation boundaries.
import { variableTrackingApi, workflowApi, type WorkflowRunSummary, type VariableTrackingRecord } from '../api'
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { SelectNative } from './controls/select-native'
import { X, Search, Filter, RefreshCw, Download, Trash2, Clock, Tag, TrendingUp, Eye, EyeOff, Activity } from 'lucide-react'

interface VariableTrackingPanelProps {
  workflowId: string
  runId?: string
  isOpen: boolean
  onClose: () => void
}

interface VariableStats {
  count: number
  firstValue: any
  lastValue: any
  operations: Record<VariableTrackingRecord['operation'], number>
  value_type: string
}

export const VariableTrackingPanel: React.FC<VariableTrackingPanelProps> = props =>
  props.isOpen ? <VariableTrackingHost key={`${props.workflowId}:${props.runId || ""}`} {...props} /> : null

const VariableTrackingHost: React.FC<VariableTrackingPanelProps> = props => {
  const [selectedRunId, setSelectedRunId] = useState(props.runId || '')
  const [runs, setRuns] = useState<WorkflowRunSummary[]>([])
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const request = useRef(0)
  const pending = useRef(false)
  useEffect(() => () => { request.current++ }, [])
  const loadRuns = async (cursor = 0) => {
    if (pending.current) return
    pending.current = true; setLoading(true)
    const current = ++request.current
    const result = await workflowApi.listRuns(undefined,cursor,50)
    if (request.current !== current) return
    pending.current = false; setLoading(false)
    if (!result.success || !result.data) { setError(result.error || '读取运行历史失败'); return }
    setRuns(previous => cursor === 0 ? result.data!.items : [...previous,...result.data!.items])
    setNextCursor(result.data.nextCursor); setError('')
  }
  const selector = <div className="flex items-center gap-2 px-6 py-2 border-b text-sm">
    <SelectNative aria-label="追踪运行" value={selectedRunId} onChange={event => setSelectedRunId(event.target.value)}>
      <option value="">当前流程（兼容记录）</option>
      {selectedRunId && !runs.some(run => run.runId === selectedRunId) && <option value={selectedRunId}>运行 {selectedRunId}</option>}
      {runs.map(run => <option key={run.runId} value={run.runId}>{run.workflowName || run.workflowId} · {run.startedAt} · {run.runId}</option>)}
    </SelectNative>
    <button disabled={loading} onClick={() => void loadRuns()}>读取运行历史</button>
    {nextCursor !== null && <button disabled={loading} onClick={() => void loadRuns(nextCursor)}>更早运行</button>}
    {error && <span role="alert">{error}</span>}
  </div>
  return <VariableTrackingContent key={selectedRunId} {...props} runId={selectedRunId || undefined} runSelector={selector}/>
}

const VariableTrackingContent: React.FC<VariableTrackingPanelProps & {runSelector: React.ReactNode}> = ({
  workflowId,
  runId,
  runSelector,
  isOpen,
  onClose
}) => {
  const [trackingRecords, setTrackingRecords] = useState<(VariableTrackingRecord & {sequence?: number; largeValues?: Record<string, string>})[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedVariable, setSelectedVariable] = useState<string | null>(null)
  const [selectedOperation, setSelectedOperation] = useState<string>('all')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [showFilters, setShowFilters] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [expandedRecords, setExpandedRecords] = useState<Set<number>>(new Set())

  const [readError, setReadError] = useState('')
  const [clearError, setClearError] = useState('')
  const [clearing, setClearing] = useState(false)
  const request = useRef<{controller:AbortController; kind:'read'|'clear'} | null>(null)

  const [page, setPage] = useState({cursor: 0, throughSequence: undefined as number | undefined})
  const [total, setTotal] = useState(0)
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const cutoff = useRef<number | undefined>(undefined)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const exportRequest = useRef<AbortController | null>(null)
  const valueRequests = useRef(new Map<string, AbortController>())
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [valueErrors, setValueErrors] = useState<Record<string, string>>({})
  const [loadingValues, setLoadingValues] = useState<Set<string>>(new Set())
  const filters = useMemo(() => runId ? {
    query: searchTerm || undefined, variable: selectedVariable || undefined,
    operation: selectedOperation === 'all' ? undefined : selectedOperation,
    valueType: selectedType === 'all' ? undefined : selectedType,
  } : {}, [runId, searchTerm, selectedVariable, selectedOperation, selectedType])
  // Legacy filters are local; only run filters initiate service reads.
  const filterKey = runId ? JSON.stringify(filters) : ''
  const confirmedFilter = useRef(filterKey)

  const fetchTrackingData = useCallback(async () => {
    if ((!workflowId && !runId) || request.current) return
    const current = {controller:new AbortController(),kind:'read' as const}
    request.current = current
    setLoading(true)
    if (runId) {
      const changed = confirmedFilter.current !== filterKey
      const result = await variableTrackingApi.listRun(runId, {
        ...JSON.parse(filterKey), limit: 100,
        cursor: changed ? 0 : page.cursor,
        throughSequence: changed ? undefined : page.throughSequence,
      }, current.controller.signal)
      if (request.current !== current || current.controller.signal.aborted) return
      request.current = null
      setLoading(false)
      if (result.success && result.data?.runId === runId) {
        setTrackingRecords(result.data.tracking); setTotal(result.data.total)
        setNextCursor(result.data.nextCursor ?? null); cutoff.current = result.data.throughSequence
        setReadError('')
        if (changed) {
          confirmedFilter.current = filterKey
          if (page.cursor !== 0 || page.throughSequence !== undefined) setPage({cursor: 0, throughSequence: undefined})
        }
      } else setReadError(result.error || '获取运行变量追踪记录失败')
    } else {
      const result = await variableTrackingApi.list(workflowId,current.controller.signal)
      if (request.current !== current || current.controller.signal.aborted) return
      request.current = null
      setLoading(false)
      if (result.success && result.data) { setTrackingRecords(result.data.tracking); setReadError('') }
      else setReadError(result.error || '获取变量追踪记录失败')
    }
  }, [workflowId, runId, filterKey, page])

  useEffect(() => {
    void fetchTrackingData()
    return () => {
      request.current?.controller.abort(); request.current = null
      valueRequests.current.forEach(controller => controller.abort()); valueRequests.current.clear()
      setValues({}); setValueErrors({}); setLoadingValues(new Set()); setExpandedRecords(new Set())
    }
  }, [fetchTrackingData])

  useEffect(() => () => {
    exportRequest.current?.abort()
    valueRequests.current.forEach(controller => controller.abort())
    valueRequests.current.clear()
  }, [])

  useEffect(() => {
    // Browsing history keeps its cutoff stable until an explicit refresh.
    if (!autoRefresh || (runId && page.throughSequence !== undefined)) return
    const interval = setInterval(() => { void fetchTrackingData() },1000)
    return () => clearInterval(interval)
  }, [autoRefresh,fetchTrackingData,runId,page.throughSequence])

  const handleRefresh = () => {
    if (runId && page.throughSequence !== undefined) setPage({cursor: 0, throughSequence: undefined})
    else void fetchTrackingData()
  }

  const handleClear = async () => {
    if ((!workflowId && !runId) || request.current?.kind === 'clear') return
    request.current?.controller.abort()
    const current = {controller:new AbortController(),kind:'clear' as const}
    request.current = current
    setLoading(false)
    setClearing(true)
    const result = runId
      ? await variableTrackingApi.clearRun(runId,current.controller.signal)
      : await variableTrackingApi.clear(workflowId,current.controller.signal)
    if (request.current !== current || current.controller.signal.aborted) return
    request.current = null
    setClearing(false)
    if (result.success) {
      setTrackingRecords([]); setExpandedRecords(new Set()); setClearError(''); setReadError('')
      setTotal(0); setNextCursor(null); cutoff.current = undefined; setValues({})
      valueRequests.current.forEach(controller => controller.abort()); valueRequests.current.clear()
      setLoadingValues(new Set()); setValueErrors({})
      if (runId) setPage({cursor: 0, throughSequence: undefined})
    } else setClearError(result.error || '清空变量追踪记录失败，已保留显示内容')
  }

  const handleExport = async () => {
    if (exportRequest.current) return
    let dataBlob: Blob
    if (runId) {
      if (cutoff.current === undefined || confirmedFilter.current !== filterKey) return
      const controller = new AbortController()
      exportRequest.current = controller; setExporting(true)
      const result = await variableTrackingApi.exportRun(runId, cutoff.current, filters, controller.signal)
      if (controller.signal.aborted) return
      exportRequest.current = null; setExporting(false)
      if (!result.success || !result.data) { setExportError(result.error || '导出变量追踪失败'); return }
      dataBlob = result.data
    } else dataBlob = new Blob([JSON.stringify(trackingRecords, null, 2)], {type:'application/json'})
    setExportError('')
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = runId ? `variable-tracking-${runId}.jsonl` : `variable-tracking-${new Date().getTime()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const loadValue = async (sequence: number, side: 'old_value' | 'new_value') => {
    if (!runId) return
    const key = `${sequence}:${side}`
    if (valueRequests.current.has(key)) return
    const controller = new AbortController()
    valueRequests.current.set(key, controller)
    setLoadingValues(previous => new Set(previous).add(key))
    const result = await variableTrackingApi.getRunValue(runId,sequence,side,controller.signal)
    if (controller.signal.aborted || valueRequests.current.get(key) !== controller) return
    valueRequests.current.delete(key)
    setLoadingValues(previous => {const next=new Set(previous);next.delete(key);return next})
    if (result.success && result.data?.runId === runId && result.data.sequence === sequence && result.data.key === side) {
      setValues(previous => ({...previous,[key]:result.data!.value}))
      setExpandedRecords(previous => new Set(previous).add(trackingRecords.findIndex(record => record.sequence === sequence)))
      setValueErrors(previous => ({...previous,[key]:''}))
    } else setValueErrors(previous => ({...previous,[key]:result.error || '完整值读取失败'}))
  }

  // 获取所有唯一的变量名
  const uniqueVariables = useMemo(() => {
    const variables = new Set(trackingRecords.map(r => r.variable_name))
    return Array.from(variables).sort()
  }, [trackingRecords])

  // 获取所有唯一的类型
  const uniqueTypes = useMemo(() => {
    const types = new Set(trackingRecords.map(r => r.value_type))
    return Array.from(types).sort()
  }, [trackingRecords])

  // 过滤记录
  const filteredRecords = useMemo(() => {
    if (runId) return trackingRecords
    return trackingRecords.filter(record => {
      // 搜索过滤
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase()
        const matchesSearch = 
          record.variable_name.toLowerCase().includes(searchLower) ||
          record.node_name.toLowerCase().includes(searchLower) ||
          JSON.stringify(record.new_value).toLowerCase().includes(searchLower)
        
        if (!matchesSearch) return false
      }

      // 变量名过滤
      if (selectedVariable && record.variable_name !== selectedVariable) {
        return false
      }

      // 操作类型过滤
      if (selectedOperation !== 'all' && record.operation !== selectedOperation) {
        return false
      }

      // 值类型过滤
      if (selectedType !== 'all' && record.value_type !== selectedType) {
        return false
      }

      return true
    })
  }, [trackingRecords, searchTerm, selectedVariable, selectedOperation, selectedType, runId])

  // 获取变量的统计信息
  const variableStats = useMemo(() => {
    const stats = new Map<string, VariableStats>()

    trackingRecords.forEach(record => {
      if (!stats.has(record.variable_name)) {
        stats.set(record.variable_name, {
          count: 0,
          firstValue: record.new_value,
          lastValue: record.new_value,
          operations: { create: 0, update: 0, scope_exit: 0 },
          value_type: record.value_type
        })
      }

      const stat = stats.get(record.variable_name)!
      stat.count++
      stat.lastValue = record.new_value
      stat.operations[record.operation]++
      stat.value_type = record.value_type
    })

    return stats
  }, [trackingRecords])

  // 切换记录展开状态
  const toggleRecordExpanded = (index: number) => {
    const newExpanded = new Set(expandedRecords)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedRecords(newExpanded)
  }

  // 格式化值显示
  const formatValue = (value: any): string => {
    if (value === null || value === undefined) {
      return 'null'
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2)
    }
    return String(value)
  }

  // 格式化时间
  const formatTime = (timestamp: string): string => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      fractionalSecondDigits: 3
    } as any)
  }

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center backdrop-blur-sm" style={{ zIndex: 2147483646 }}>
      <div className="bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300">
        
        {/* 头部 */}
        <div className="bg-[hsl(var(--card))] flex items-center justify-between px-6 py-4 border-b border-gray-200 to-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shadow-lg bg-[hsl(var(--info-500))]/10 border border-[hsl(var(--info-500))]/30">
              <Activity className="w-5 h-5 text-[hsl(var(--info-500))]" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-800">变量追踪</h2>
              <p className="text-sm text-gray-500">
                {runId ? `共 ${total} 条记录，本页 ${trackingRecords.length} 条` : `共 ${trackingRecords.length} 条记录，显示 ${filteredRecords.length} 条`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* 自动刷新开关 */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200
                ${autoRefresh 
                  ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              title={autoRefresh ? '关闭自动刷新' : '开启自动刷新'}
            >
              <RefreshCw className={`w-4 h-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            </button>

            {/* 手动刷新 */}
            <button
              onClick={handleRefresh}
              disabled={loading || clearing}
              className="px-3 py-2 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 
                transition-all duration-200 disabled:opacity-50"
              title="手动刷新"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            {/* 导出 */}
            <button
              onClick={handleExport}
              disabled={trackingRecords.length === 0 || exporting || (Boolean(runId) && (loading || confirmedFilter.current !== filterKey))}
              className="px-3 py-2 rounded-lg bg-purple-100 text-purple-700 hover:bg-purple-200 
                transition-all duration-200 disabled:opacity-50"
              title={runId ? "导出JSONL" : "导出JSON"}
            >
              <Download className="w-4 h-4" />
            </button>

            {/* 清空 */}
            <button
              onClick={handleClear}
              disabled={(runId ? total === 0 : trackingRecords.length === 0) || clearing}
              className="px-3 py-2 rounded-lg bg-red-100 text-red-700 hover:bg-red-200 
                transition-all duration-200 disabled:opacity-50"
              title="清空记录"
            >
              <Trash2 className="w-4 h-4" />
            </button>

            {/* 关闭 */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors has-hover-only"
              title="关闭"
            >
              <X className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>

        {runSelector}
        {(readError || clearError || exportError) && <div role="alert" className="px-6 py-3 text-red-700 bg-red-50">{clearError || exportError || readError}</div>}
        {clearing && <div role="status" className="px-6 py-2">正在等待服务确认清空记录…</div>}
        {/* 工具栏 */}
        <fieldset disabled={clearing} className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            {/* 搜索框 */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="搜索变量名、模块名或值..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 
                  focus:ring-orange-500 focus:border-transparent transition-all"
              />
            </div>

            {/* 过滤器按钮 */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`px-4 py-2 rounded-lg font-medium transition-all duration-200 flex items-center gap-2
                ${showFilters 
                  ? 'bg-orange-100 text-orange-700' 
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'}`}
            >
              <Filter className="w-4 h-4" />
              过滤器
            </button>
          </div>

          {/* 过滤器面板 */}
          {showFilters && (
            <div className="mt-3 p-4 bg-white rounded-lg border border-gray-200 grid grid-cols-3 gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
              
              {/* 变量名过滤 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">变量名</label>
                <SelectNative
                  aria-label="变量名"
                  value={selectedVariable || ''}
                  onChange={(e) => setSelectedVariable(e.target.value || null)}
                >
                  <option value="">全部变量</option>
                  {uniqueVariables.map(variable => (
                    <option key={variable} value={variable}>
                      {variable} ({variableStats.get(variable)?.count || 0})
                    </option>
                  ))}
                </SelectNative>
              </div>

              {/* 操作类型过滤 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">操作类型</label>
                <SelectNative
                  aria-label="操作类型"
                  value={selectedOperation}
                  onChange={(e) => setSelectedOperation(e.target.value)}
                >
                  <option value="all">全部操作</option>
                  <option value="create">创建</option>
                  <option value="update">更新</option>
                  <option value="scope_exit">退出作用域</option>
                </SelectNative>
              </div>

              {/* 值类型过滤 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">值类型</label>
                <SelectNative
                  aria-label="值类型"
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                >
                  <option value="all">全部类型</option>
                  {uniqueTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </SelectNative>
              </div>
            </div>
          )}
        </fieldset>

        {runId && <div className="flex items-center gap-3 px-6 py-2 border-b">
          <span>本页统计；运行 {runId}</span>
          <button disabled={loading || clearing || page.cursor === 0} onClick={() => setPage({cursor:0,throughSequence:cutoff.current})}>第一页</button>
          <button disabled={loading || clearing || nextCursor === null} onClick={() => setPage({cursor:nextCursor!,throughSequence:cutoff.current})}>下一页</button>
        </div>}
        {/* 主内容区 */}
        <div className="flex-1 overflow-hidden flex">
          
          {/* 左侧：变量列表 */}
          <div className="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto">
            <div className="p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Tag className="w-4 h-4" />
                {runId ? "本页变量" : "变量列表"} ({uniqueVariables.length})
              </h3>
              <div className="space-y-1">
                {uniqueVariables.map(variable => {
                  const stats = variableStats.get(variable)!
                  const isSelected = selectedVariable === variable
                  
                  return (
                    <button
                      key={variable}
                      disabled={clearing}
                      onClick={() => setSelectedVariable(isSelected ? null : variable)}
                      className={`w-full text-left px-3 py-2 rounded-lg transition-all duration-200
                        ${isSelected 
                          ? 'bg-orange-100 text-orange-700 shadow-sm' 
                          : 'hover:bg-white text-gray-700 has-hover-only'}`}
                    >
                      <div className="font-medium text-sm truncate">{variable}</div>
                      <div className="text-xs text-gray-500 mt-1 flex items-center justify-between">
                        <span>{runId ? "本页 " : ""}{stats.count} 次变化</span>
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200">
                          {stats.value_type}
                        </span>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {/* 右侧：追踪记录 */}
          <div className="flex-1 overflow-y-auto">
            {filteredRecords.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <TrendingUp className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">{trackingRecords.length || (runId && (searchTerm || selectedVariable || selectedOperation !== 'all' || selectedType !== 'all')) ? '没有匹配的追踪记录' : '暂无追踪记录'}</p>
                <p className="text-sm mt-2">{trackingRecords.length || (runId && (searchTerm || selectedVariable || selectedOperation !== 'all' || selectedType !== 'all')) ? '请调整搜索内容或筛选条件' : '运行工作流后将显示变量变化'}</p>
              </div>
            ) : (
              <div className="p-6 space-y-3">
                {filteredRecords.map((record, index) => {
                  const isExpanded = expandedRecords.has(index)
                  const displayValue = (side: 'old_value' | 'new_value') => {
                    const key = `${record.sequence}:${side}`
                    return Object.hasOwn(values,key) ? formatValue(values[key]) : record.largeValues?.[side] ?? formatValue(record[side])
                  }
                  const oldValueStr = displayValue('old_value')
                  const newValueStr = displayValue('new_value')
                  const valueButton = (side: 'old_value' | 'new_value') => {
                    if (!runId || record.sequence === undefined || !Object.hasOwn(record.largeValues || {},side)) return null
                    const key = `${record.sequence}:${side}`
                    return <>{!Object.hasOwn(values,key) && <button type="button" disabled={loadingValues.has(key)} className="text-sm underline" onClick={() => void loadValue(record.sequence!,side)}>
                      {loadingValues.has(key) ? '读取中…' : `读取完整${side === 'old_value' ? '旧' : '新'}值`}
                    </button>}{valueErrors[key] && <div role="alert">{valueErrors[key]}</div>}</>
                  }
                  const isLongValue = newValueStr.length > 100 || oldValueStr.length > 100

                  return (
                    <div
                      key={index}
                      className="bg-white rounded-lg border border-gray-200 hover:border-orange-300 transition-all duration-200 hover:shadow-md overflow-hidden"
                    >
                      <div className="p-4">
                        {/* 记录头部 */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${
                              record.operation === 'create' ? 'bg-green-500' : record.operation === 'scope_exit' ? 'bg-gray-500' : 'bg-blue-500'
                            }`} />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-gray-800">
                                  {record.variable_name}
                                </span>
                                <span className={`text-xs px-2 py-0.5 rounded-control font-medium ${
                                  record.operation === 'create'
                                    ? 'bg-green-100 text-green-700' 
                                    : record.operation === 'scope_exit'
                                      ? 'bg-gray-100 text-gray-700'
                                      : 'bg-blue-100 text-blue-700'
                                }`}>
                                  {record.operation === 'create' ? '创建' : record.operation === 'scope_exit' ? '退出作用域' : '更新'}
                                </span>
                                <span className="text-xs px-2 py-0.5 rounded-control bg-gray-100 text-gray-600">
                                  {record.value_type}
                                </span>
                              </div>
                              <div className="text-sm text-gray-500 mt-1 flex items-center gap-2">
                                <Clock className="w-3 h-3" />
                                {formatTime(record.timestamp)}
                                <span className="mx-1">•</span>
                                {record.node_name}
                              </div>
                            </div>
                          </div>

                          {isLongValue && (
                            <button
                              onClick={() => toggleRecordExpanded(index)}
                              className="p-1 rounded hover:bg-gray-100 transition-colors has-hover-only"
                              title={isExpanded ? '收起' : '展开'}
                            >
                              {isExpanded ? (
                                <EyeOff className="w-4 h-4 text-gray-600" />
                              ) : (
                                <Eye className="w-4 h-4 text-gray-600" />
                              )}
                            </button>
                          )}
                        </div>

                        {/* 值变化 */}
                        <div className="space-y-2">
                          {record.operation !== 'create' && (
                            <div className="bg-red-50 rounded-lg p-3 border border-red-100">
                              <div className="text-xs font-medium text-red-700 mb-1">旧值</div>
                              <pre className={`text-sm text-red-800 font-mono whitespace-pre-wrap break-all ${
                                !isExpanded && isLongValue ? 'line-clamp-2' : ''
                              }`}>
                                {oldValueStr}
                              </pre>
                              {valueButton("old_value")}
                            </div>
                          )}

                          <div className="bg-green-50 rounded-lg p-3 border border-green-100">
                            <div className="text-xs font-medium text-green-700 mb-1">新值</div>
                            <pre className={`text-sm text-green-800 font-mono whitespace-pre-wrap break-all ${
                              !isExpanded && isLongValue ? 'line-clamp-2' : ''
                            }`}>
                              {newValueStr}
                            </pre>
                            {valueButton("new_value")}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
