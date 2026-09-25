import { ProjectLifecycleConfig } from './config-panels/ProjectLifecycleConfig'
import { ProjectDataConfig } from './config-panels/ProjectDataConfig'

import { ProxyControlConfig } from './config-panels/ProxyControlConfig'
import { excludedModuleTypes } from '../lib/moduleCatalog'
// Source: WebRPA@5ccb900e, components/workflow/ConfigPanel.tsx; see SOURCE.md for license and adaptation boundaries.
import { useWorkflowStore, moduleTypeLabels, getModuleDefaultTimeout, type NodeData, type ErrorPolicy } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { ScrollArea } from './controls/scroll-area'
import { useRequiredFields, getMissingRequiredLabels } from '../lib/requiredFields'
import { emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { Input } from './controls/input'
import { NumberInput } from './controls/number-input'
import { Label } from './controls/label'
import { SelectNative as Select } from './controls/select-native'
import { Button } from './controls/button'
import { VariableInput } from './controls/variable-input'
import { Trash2, Crosshair, Loader2, Ban, ChevronLeft, ChevronRight, Settings, Sparkles, ScanSearch } from 'lucide-react'
import { moduleIcons } from './ModuleSidebar'
import { useState, useCallback, useRef, useEffect } from 'react'
import { elementPickerApi, systemApi } from '../api'
import { getStudioTransportRevision } from '../api/transport'

// 导入拆分的配置组件
import {
  DpOpenPageConfig, DpClickConfig, DpInputConfig, DpGetTextConfig, DpGetHtmlConfig,
  DpRunJsConfig, DpWaitElementConfig, DpScrollConfig, DpCloseConfig,
} from './config-panels/DrissionPageConfigs'
import { RunWorkflowFileConfig } from './config-panels/RunWorkflowFileConfig'
import { SimilarSelectorDialog } from './config-panels/SimilarSelectorDialog'
import { UrlInputDialog } from './config-panels/UrlInputDialog'
import { OpenPageConfig, UseOpenedPageConfig, ClickElementConfig, HoverElementConfig, InputTextConfig, GetElementInfoConfig, WaitConfig, WaitElementConfig, WaitPageLoadConfig, PageLoadCompleteConfig, SetVariableConfig, IncrementDecrementConfig, PrintLogConfig, PlaySoundConfig, SystemNotificationConfig, InputPromptConfig, TextToSpeechConfig, JsScriptConfig, PythonScriptConfig, ExtractTableDataConfig, SwitchTabConfig, GroupConfig, SubflowHeaderConfig, RefreshPageConfig, GoBackConfig, GoForwardConfig, HandleDialogConfig, InjectJavaScriptConfig, SwitchIframeConfig, SwitchToMainConfig } from './config-panels/BasicModuleConfigs'
import { SelectDropdownConfig, SetCheckboxConfig, DragElementConfig, ScrollPageConfig, UploadFileConfig, DownloadFileConfig, SaveImageConfig, GetChildElementsConfig, GetSiblingElementsConfig, ScreenshotConfig, OCRCaptchaConfig, SliderCaptchaConfig, SendEmailConfig, SetClipboardConfig, GetClipboardConfig, ShutdownSystemConfig, LockScreenConfig, RunCommandConfig, NetworkCaptureConfig, ElementExistsConfig, ElementVisibleConfig, NetworkMonitorStartConfig, NetworkMonitorWaitConfig, NetworkMonitorStopConfig } from './config-panels/AdvancedModuleConfigs'
import {
  AIChatConfig,
  AITaskConfig,
  AIVisionConfig,
  AIVisionActConfig,
  ApiRequestConfig,
  AISmartScraperConfig,
  AIElementSelectorConfig,
  FirecrawlScrapeConfig,
  FirecrawlMapConfig,
  FirecrawlCrawlConfig,
} from './config-panels/AIModuleConfigs'
import {
  ConditionConfig,
  LoopConfig,
  InfiniteLoopConfig,
  ForeachConfig,
  ForeachDictConfig,
  ScheduledTaskConfig,
  SubflowConfig,
  AssertCheckpointConfig,
} from './config-panels/ControlModuleConfigs'
import {
  WebhookTriggerConfig,
  HotkeyTriggerConfig,
  FileWatcherTriggerConfig,
  EmailTriggerConfig,
  ApiTriggerConfig,
  MouseTriggerConfig,
  ImageTriggerConfig,
  SoundTriggerConfig,
  FaceTriggerConfig,
  ElementChangeTriggerConfig,
  GestureTriggerConfig,
} from './config-panels/TriggerModuleConfigs'
import {
  RegexExtractConfig,
  StringReplaceConfig,
  StringSplitConfig,
  StringJoinConfig,
  StringConcatConfig,
  StringTrimConfig,
  StringCaseConfig,
  StringSubstringConfig,
  JsonParseConfig,
  Base64Config,
  RandomNumberConfig,
  GetTimeConfig,
  ListOperationConfig,
  ListGetConfig,
  ListLengthConfig,
  ListExportConfig,
  DictOperationConfig,
  DictGetConfig,
  DictKeysConfig,
  TableAddRowConfig,
  TableAddColumnConfig,
  TableSetCellConfig,
  TableGetCellConfig,
  TableDeleteRowConfig,
  TableClearConfig,
  TableExportConfig,
} from './config-panels/DataModuleConfigs'
import {
  ListSumConfig,
  ListAverageConfig,
  ListMaxConfig,
  ListMinConfig,
  ListSortConfig,
  ListUniqueConfig,
  ListSliceConfig,
  MathRoundConfig,
  MathBaseConvertConfig,
  MathFloorConfig,
  MathModuloConfig,
  MathAbsConfig,
  MathSqrtConfig,
  MathPowerConfig,
} from './config-panels/MathListConfigs'
import {
  ListReverseConfig,
  ListFindConfig,
  ListCountConfig,
  ListFilterConfig,
  ListMapConfig,
  ListMergeConfig,
  ListFlattenConfig,
  ListChunkConfig,
  ListRemoveEmptyConfig,
  ListIntersectionConfig,
  ListUnionConfig,
  ListDifferenceConfig,
  ListCartesianProductConfig,
  ListShuffleConfig,
  ListSampleConfig,
} from './config-panels/ListAdvancedConfigs'
import {
  DictMergeConfig,
  DictFilterConfig,
  DictMapValuesConfig,
  DictInvertConfig,
  DictSortConfig,
  DictDeepCopyConfig,
  DictGetPathConfig,
  DictFlattenConfig,
} from './config-panels/DictAdvancedConfigs'
import {
  MathLogConfig,
  MathTrigConfig,
  MathExpConfig,
  MathGcdConfig,
  MathLcmConfig,
  MathFactorialConfig,
  MathPermutationConfig,
  MathPercentageConfig,
  MathClampConfig,
  MathRandomAdvancedConfig,
} from './config-panels/MathAdvancedConfigs'
import {
  StatMedianConfig,
  StatModeConfig,
  StatVarianceConfig,
  StatStdevConfig,
  StatPercentileConfig,
  StatNormalizeConfig,
  StatStandardizeConfig,
  CsvParseConfig,
  CsvGenerateConfig,
  ListToStringAdvancedConfig,
} from './config-panels/StatisticsConfigs'
import {
  DbConnectConfig,
  DbQueryConfig,
  DbExecuteConfig,
  DbInsertConfig,
  DbUpdateConfig,
  DbDeleteConfig,
  DbCloseConfig,
} from './config-panels/DatabaseModuleConfigs'
import { FaceRecognitionConfig, ImageOCRConfig } from './config-panels/MediaModuleConfigs'
import { NotifyDiscordConfig, NotifyTelegramConfig, NotifyDingTalkConfig, NotifyWeComConfig, NotifyBarkConfig, NotifySlackConfig, NotifyMSTeamsConfig, NotifyPushoverConfig, NotifyPushBulletConfig, NotifyGotifyConfig, NotifyServerChanConfig, NotifyPushPlusConfig, NotifyWebhookConfig, NotifyNtfyConfig, NotifyMatrixConfig, NotifyRocketChatConfig } from './config-panels/NotifyModuleConfigs'
import { WebhookRequestConfig, OracleConnectConfig, OracleQueryConfig, OracleExecuteConfig, PostgreSQLConnectConfig, PostgreSQLQueryConfig, PostgreSQLExecuteConfig, MongoDBConnectConfig, MongoDBFindConfig, MongoDBInsertConfig, MongoDBUpdateConfig, MongoDBDeleteConfig, SQLServerConnectConfig, SQLServerQueryConfig, SQLServerExecuteConfig, SQLiteConnectConfig, SQLiteQueryConfig, SQLiteExecuteConfig, RedisConnectConfig, RedisGetConfig, RedisSetConfig, RedisDelConfig, RedisHGetConfig, RedisHSetConfig, OracleInsertConfig, OracleUpdateConfig, OracleDeleteConfig, PostgreSQLInsertConfig, PostgreSQLUpdateConfig, PostgreSQLDeleteConfig, SQLServerInsertConfig, SQLServerUpdateConfig, SQLServerDeleteConfig, SQLiteInsertConfig, SQLiteUpdateConfig, SQLiteDeleteConfig, OracleDisconnectConfig, PostgreSQLDisconnectConfig, MongoDBDisconnectConfig, SQLServerDisconnectConfig, SQLiteDisconnectConfig, RedisDisconnectConfig, SSHConnectConfig, SSHExecuteCommandConfig, SSHUploadFileConfig, SSHDownloadFileConfig, SSHDisconnectConfig, AIGenerateImageConfig, AIGenerateVideoConfig, ProbabilityTriggerConfig } from './config-panels/index'
import {
  AllureInitConfig,
  AllureStartTestConfig,
  AllureAddStepConfig,
  AllureAddAttachmentConfig,
  AllureStopTestConfig,
  AllureGenerateReportConfig,
} from './config-panels/TestAllureConfigs'
import { ExportLogConfig, ShareFolderConfig, ShareFileConfig, StopShareConfig, StartScreenShareConfig, StopScreenShareConfig } from './config-panels/AdvancedModuleConfigs'
import { RandomPasswordGeneratorConfig, URLEncodeDecodeConfig, MD5EncryptConfig, SHAEncryptConfig, TimestampConverterConfig, RGBToHSVConfig, RGBToCMYKConfig, HEXToCMYKConfig, UUIDGeneratorConfig, PrinterCallConfig } from './config-panels/UtilityToolsConfigs'
import { CustomModuleConfig } from './config-panels/CustomModuleConfig'
import { PanelResizer } from './PanelResizer'
import { useLayoutStore, LAYOUT_LIMITS } from '../hooks/stores/layoutStore'

interface ConfigPanelProps {
  selectedNodeId?: string | null  // 改为可选，优先使用 store 中的值
}

/** 把选择器写入系统剪贴板。
 * 拾取元素时焦点在自动化浏览器窗口、编辑器失焦，navigator.clipboard 会以
 * "document is not focused" 拒绝复制，故改由后端写系统剪贴板（焦点无关）。
 * 后端不可用时兜底尝试浏览器 Clipboard API。返回是否成功。 */
async function writeSelectorToClipboard(text: string): Promise<boolean> {
  try {
    const res = await systemApi.setClipboard(text)
    if (!res.error) return true
  } catch { /* 落到下方浏览器兜底 */ }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-999999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
    return true
  } catch {
    return false
  }
}

export function ConfigPanel({ selectedNodeId: propSelectedNodeId }: ConfigPanelProps) {
  // 直接从 store 订阅 selectedNodeId，确保实时更新
  const storeSelectedNodeId = useWorkflowStore((state) => state.selectedNodeId)
  const selectedNodeId = propSelectedNodeId ?? storeSelectedNodeId
  
  const nodes = useWorkflowStore((state) => state.nodes)
  const documentId = useWorkflowStore((state) => state.id)
  const requiredFields = useRequiredFields()
  const updateNodeData = useWorkflowStore((state) => state.updateNodeData)
  const deleteNode = useWorkflowStore((state) => state.deleteNode)
  const addLog = useWorkflowStore((state) => state.addLog)
  const toggleNodesDisabled = useWorkflowStore((state) => state.toggleNodesDisabled)
  
  // 获取浏览器配置
  const browserConfig = useGlobalConfigStore((state) => state.config.browser)

  const [isPicking, setIsPicking] = useState(false)
  const [pickingField, setPickingField] = useState<string | null>(null)
  const [testingField, setTestingField] = useState<string | null>(null)
  const selectorTestSequence = useRef(0)
  const pickerSequence = useRef(0)
  const pickerActive = useRef(false)
  const pickerConnection = useRef<number | null>(null)
  const pickerContext = useRef<(() => boolean) | null>(null)
  useEffect(() => {
    selectorTestSequence.current += 1
    setTestingField(null)
    return () => { selectorTestSequence.current += 1 }
  }, [selectedNodeId, documentId])
  // 选择器类型偏好（CSS/XPath）。用于在选择器值为空时也能正确切换模式，避免污染数据
  const [selectorTypeOverride, setSelectorTypeOverride] = useState<Record<string, 'css' | 'xpath'>>({})
  const [showUrlDialog, setShowUrlDialog] = useState(false)
  const [pickerUrl, setPickerUrl] = useState('')
  const [pendingField, setPendingField] = useState<string | null>(null)
  const [isCollapsed, setIsCollapsed] = useState(false)
  // 受 layoutStore 控制的宽度（用户可拖拽）
  const rightWidth = useLayoutStore((s) => s.rightWidth)
  const setRightWidth = useLayoutStore((s) => s.setRightWidth)
  const [draftRightWidth, setDraftRightWidth] = useState<number | null>(null)
  const effectiveRightWidth = draftRightWidth ?? rightWidth
  const pollingRef = useRef<number | null>(null)
  
  // 响应式：小屏幕自动折叠
  useEffect(() => {
    const handleResize = () => {
      // 屏幕宽度小于1280px时自动折叠
      if (window.innerWidth < 1280) {
        setIsCollapsed(true)
      }
    }

    // 初始检查
    handleResize()

    // 监听窗口大小变化
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])
  
  // 相似元素选择状态
  const [showSimilarDialog, setShowSimilarDialog] = useState(false)
  const [similarResult, setSimilarResult] = useState<{
    pattern: string
    count: number
    minIndex: number
    maxIndex: number
  } | null>(null)

  const selectedNode = nodes.find((n) => n.id === selectedNodeId)
  const nodeData = selectedNode?.data as NodeData | undefined

  // Invalidate every awaited picker response when the owning document/panel changes.
  useEffect(() => {
    setIsPicking(false)
    setPickingField(null)
    setShowSimilarDialog(false)
    setSimilarResult(null)
    setShowUrlDialog(false)
    setPendingField(null)
    setSelectorTypeOverride({})
    return () => {
      pickerSequence.current += 1
      pickerContext.current = null
      if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
      if (pickerActive.current) {
        pickerActive.current = false
        if (pickerConnection.current === getStudioTransportRevision()) void elementPickerApi.stop().catch(() => {})
      }
    }
  }, [selectedNodeId, documentId])

  const handleChange = useCallback((key: string, value: unknown) => {
    if (selectedNodeId) {
      updateNodeData(selectedNodeId, { [key]: value })
    }
  }, [selectedNodeId, updateNodeData])

  const handleBatchChange = useCallback((data: Partial<NodeData>) => {
    if (selectedNodeId) updateNodeData(selectedNodeId, data)
  }, [selectedNodeId, updateNodeData])

  const handleDelete = () => {
    if (selectedNodeId) {
      deleteNode(selectedNodeId)
    }
  }

  // 选中节点"问 AI"：让小助手解释/优化/修复当前模块
  const askAIAboutNode = () => {
    if (!nodeData) return
    const mt = String(nodeData.moduleType)
    const label = String(moduleTypeLabels[mt as keyof typeof moduleTypeLabels] ?? mt)
    // 精简配置（去掉内部字段）
    const skip = new Set(['moduleType', 'label', 'isHighlighted', '__aiSpawning'])
    const cfg: Record<string, unknown> = {}
    Object.entries(nodeData as Record<string, unknown>).forEach(([k, v]) => {
      if (skip.has(k)) return
      if (v === '' || v === undefined || v === null) return
      cfg[k] = v
    })
    let cfgStr = ''
    try { cfgStr = JSON.stringify(cfg) } catch { cfgStr = '(无法序列化)' }
    if (cfgStr.length > 1200) cfgStr = cfgStr.slice(0, 1200) + '…'
    const prompt = `请帮我看下当前工作流里这个模块：\n` +
      `模块类型：${label}（${mt}）\n` +
      `节点备注：${(nodeData.name as string) || '无'}\n` +
      `当前配置：${cfgStr}\n\n` +
      `请：1) 简要说明它的作用；2) 指出配置是否有问题或可优化之处；3) 给出具体修改建议。`
    emitAssistantUiEvent('ask_ai', { prompt, autoSend: true })
  }

  const pickerStopPending = useRef(false)
  const confirmPickerStop = useCallback(async (request: number) => {
    if (pickerStopPending.current) return false
    if (pickerConnection.current !== getStudioTransportRevision()) {
      addLog({level:'error',message:'拾取所属连接已变更，请在当前浏览器面板确认会话状态'})
      return false
    }
    pickerStopPending.current = true
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
    setShowSimilarDialog(false)
    setSimilarResult(null)
    try {
      const result = await elementPickerApi.stop()
      if (request !== pickerSequence.current) return false
      if (!result.success) throw new Error(result.error || '服务未确认停止')
      pickerActive.current = false
      setIsPicking(false)
      setPickingField(null)
      return true
    } catch (error) {
      if (request === pickerSequence.current) {
        setIsPicking(true)
        addLog({ level: 'error', message: `停止元素选择器失败：${error instanceof Error ? error.message : String(error)}；请重试停止` })
      }
      return false
    } finally { pickerStopPending.current = false }
  }, [addLog])

  // 打开URL输入对话框
  const openUrlDialog = useCallback((fieldName: string) => {
    const openPageNode = nodes.find(n => (n.data as NodeData).moduleType === 'open_page')
    const defaultUrl = (openPageNode?.data as NodeData)?.url as string || ''
    setPickerUrl(defaultUrl)
    setPendingField(fieldName)
    setShowUrlDialog(true)
  }, [nodes])

  // 解析URL中的变量引用
  const resolveVariables = useCallback((value: string): string => {
    const variables = useWorkflowStore.getState().variables
    return value.replace(/\{([^}]+)\}/g, (match, varName) => {
      const variable = variables.find(v => v.name === varName.trim())
      return variable ? String(variable.value ?? '') : match
    })
  }, [])

  // 启动元素选择器
  const startElementPicker = useCallback(async (fieldName: string, url: string) => {
    const request = ++pickerSequence.current
    const state = useWorkflowStore.getState()
    const originNode = state.nodes.find(node => node.id === selectedNodeId)
    if (!originNode) return
    const originDocument = state.id
    const connection = getStudioTransportRevision()
    pickerConnection.current = connection
    const target = JSON.stringify([originNode.data[fieldName], originNode.data.selectorHints ?? null])
    const isCurrent = () => {
      const current = useWorkflowStore.getState()
      const node = current.nodes.find(node => node.id === originNode.id)
      return connection === getStudioTransportRevision() && request === pickerSequence.current && current.id === originDocument && !!node &&
        JSON.stringify([node.data[fieldName], node.data.selectorHints ?? null]) === target
    }
    pickerContext.current = isCurrent
    pickerActive.current = true
    const resolvedUrl = url ? resolveVariables(url) : ''
    setIsPicking(true)
    setPickingField(fieldName)
    setShowUrlDialog(false)
    
    if (resolvedUrl) {
      addLog({ level: 'info', message: `正在启动元素选择器，URL: ${resolvedUrl}` })
    } else {
      addLog({ level: 'info', message: '正在启动元素选择器（使用当前页面）' })
    }

    try {
      // 传递浏览器配置
      const result = await elementPickerApi.start(resolvedUrl || undefined)
      if (!isCurrent()) return
      if (result.error || !result.success) {
        if (result.outcomeUnknown) {
          addLog({level:'error',message:`拾取启动状态尚未确认：${result.error}；请重试停止以确认清理`})
          return
        }
        pickerActive.current = false
        addLog({ level: 'error', message: `启动失败: ${result.error}` })
        setIsPicking(false)
        setPickingField(null)
        return
      }

      addLog({ level: 'success', message: '元素选择器已启动：Ctrl+点击单选，Alt+点击选择相似元素' })

      let polling = false
      let pollingError: string | null = null
      pollingRef.current = window.setInterval(async () => {
        if (polling || !isCurrent()) return
        polling = true
        try {
          const selectedResult = await elementPickerApi.getSelected()
          if (!isCurrent()) return
          if (!selectedResult.success) throw new Error(selectedResult.error || '服务未确认拾取结果')

          if (selectedResult.data?.active === false) {
            pickerActive.current = false
            if (pollingRef.current) {
              clearInterval(pollingRef.current)
              pollingRef.current = null
            }
            setIsPicking(false)
            setPickingField(null)
            return
          }

          if (selectedResult.data?.selected && selectedResult.data.element) {
            const el = selectedResult.data.element
            const selector = el.selector
            if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
            updateNodeData(originNode.id, {
              [fieldName]: selector,
              ...(fieldName === 'selector' ? { selectorHints: {
                tag: el.tagName || '', text: el.text || '', attributes: (el.attributes || {}) as Record<string, unknown>,
              } } : {}),
            })
            addLog({ level: 'success', message: `已选择元素: ${selector}` })
            // 自动复制选择器到剪贴板（全局配置，默认开启）
            if (selector && browserConfig?.autoCopySelector !== false) {
              const ok = await writeSelectorToClipboard(selector)
              if (request !== pickerSequence.current) return
              addLog({ level: ok ? 'success' : 'warning', message: ok ? '选择器已复制到剪贴板' : '选择器复制到剪贴板失败' })
            }

            await confirmPickerStop(request)
            return
          }

          const similarRes = await elementPickerApi.getSimilar()
          if (!isCurrent()) return
          if (!similarRes.success) throw new Error(similarRes.error || '服务未确认相似元素结果')
          if (similarRes.data?.selected && similarRes.data.similar) {
            const similar = similarRes.data.similar
            addLog({ level: 'success', message: `找到 ${similar.count} 个相似元素` })

            setSimilarResult({
              pattern: similar.pattern,
              count: similar.count,
              minIndex: similar.minIndex,
              maxIndex: similar.maxIndex,
            })
            setShowSimilarDialog(true)

            if (pollingRef.current) {
              clearInterval(pollingRef.current)
              pollingRef.current = null
            }
          }
          if (pollingError) {
            addLog({ level: 'info', message: '拾取结果读取已恢复' })
            pollingError = null
          }
        } catch (error) {
          if (!isCurrent()) return
          const message = error instanceof Error ? error.message : String(error)
          if (pollingError !== message) {
            addLog({ level: 'error', message: `读取拾取结果失败: ${message}` })
            pollingError = message
          }
        } finally { polling = false }
      }, 500)

    } catch (error) {
      if (!isCurrent()) return
      pickerActive.current = false
      addLog({ level: 'error', message: `启动元素选择器失败: ${error}` })
      setIsPicking(false)
      setPickingField(null)
    }
  }, [addLog, updateNodeData, selectedNodeId, resolveVariables, browserConfig, confirmPickerStop])

  // 确认相似元素选择
  const handleSimilarConfirm = useCallback(async (variableName: string) => {
    if (!similarResult || !pickingField) return
    if (!pickerContext.current?.()) {
      setShowSimilarDialog(false); setSimilarResult(null)
      addLog({ level: 'warning', message: '拾取目标已变化，请重新拾取。' })
      return
    }
    const request = pickerSequence.current
    
    const finalSelector = similarResult.pattern.replace('{index}', `{${variableName}}`)
    const state = useWorkflowStore.getState()
    const existing = state.variables.some(variable => variable.name === variableName)
    const variables = existing
      ? state.variables.map(variable => variable.name === variableName ? { ...variable, value: similarResult.minIndex } : variable)
      : [...state.variables, { name: variableName, value: similarResult.minIndex, type: 'number' as const, scope: 'global' as const }]
    state.updateNodesData([{ nodeId: selectedNodeId!, data: { [pickingField]: finalSelector } }], variables)

    addLog({ 
      level: 'success', 
      message: `已设置相似元素选择器，变量 ${variableName} 范围: ${similarResult.minIndex}-${similarResult.maxIndex}` 
    })
    // 自动复制选择器到剪贴板（全局配置，默认开启）
    if (browserConfig?.autoCopySelector !== false) {
      const ok = await writeSelectorToClipboard(finalSelector)
      if (request !== pickerSequence.current) return
      addLog({ level: ok ? 'success' : 'warning', message: ok ? '选择器已复制到剪贴板' : '选择器复制到剪贴板失败' })
    }
    
    await confirmPickerStop(request)
  }, [similarResult, pickingField, selectedNodeId, addLog, browserConfig, confirmPickerStop])

  // 停止元素选择器
  const stopElementPicker = useCallback(async () => {
    if (pickerStopPending.current) return
    const request = ++pickerSequence.current
    pickerContext.current = null
    if (await confirmPickerStop(request)) addLog({ level: 'info', message: '元素选择器已停止' })
  }, [addLog, confirmPickerStop])

  if (!selectedNode || !nodeData) {
    return (
      <aside
        className="relative border-l border-[hsl(var(--border))] bg-[hsl(var(--card))] flex flex-col"
        style={{
          width: isCollapsed ? 48 : effectiveRightWidth,
          transition: draftRightWidth === null ? 'width 200ms ease-out' : 'none',
        }}
      >
        {isCollapsed ? (
          <button 
            type="button"
            className="flex flex-col items-center py-3 gap-2 hover:bg-[hsl(var(--muted))] transition-colors h-full w-full"
            onClick={() => setIsCollapsed(false)}
            title="展开配置面板"
          >
            <span className="flex items-center justify-center w-7 h-7 rounded-md bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-600))]">
              <ChevronLeft className="w-4 h-4" />
            </span>
            <Settings className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        ) : (
          <>
            <div className="p-4 border-b border-[hsl(var(--border))] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex items-center justify-center w-7 h-7 rounded-md bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-600))]">
                  <Settings className="w-4 h-4" />
                </span>
                <h2 className="text-sm font-semibold text-[hsl(var(--foreground))]">配置面板</h2>
              </div>
              <button
                onClick={() => setIsCollapsed(true)}
                className="p-1.5 rounded-md text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))] transition-colors has-hover-only"
                title="收起"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 flex items-center justify-center p-4">
              <div className="text-center animate-fade-in">
                <div className="bg-[hsl(var(--card))] w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center">
                  <Crosshair className="w-8 h-8 text-muted-foreground/40" />
                </div>
                <p className="text-sm text-muted-foreground">
                  选择一个节点查看配置
                </p>
              </div>
            </div>
          </>
        )}
        {!isCollapsed && (
          <PanelResizer
            direction="horizontal"
            side="left"
            size={effectiveRightWidth}
            minSize={LAYOUT_LIMITS.right.min}
            maxSize={LAYOUT_LIMITS.right.max}
            factor={-1}
            onLive={(w) => setDraftRightWidth(w)}
            onCommit={(w) => {
              setRightWidth(w)
              setDraftRightWidth(null)
            }}
          />
        )}
      </aside>
    )
  }

  // 渲染带选择器按钮的输入框
  // 测试选择器：在当前浏览器页面上验证是否命中并高亮（普通函数，避免在提前 return 之后调用 Hook）
  const handleTestSelector = async (id: string) => {
    const selector = (nodeData[id] as string) || ''
    if (!selector.trim()) {
      addLog({ level: 'warning', nodeId: selectedNodeId || undefined, message: '选择器为空，无法测试' })
      return
    }
    const request = ++selectorTestSequence.current
    const originDocument = useWorkflowStore.getState().id
    const originNode = selectedNodeId
    const hints = (nodeData['selectorHints'] as Record<string, unknown>) || undefined
    const target = JSON.stringify([selector, hints ?? null])
    const isCurrent = () => {
      const state = useWorkflowStore.getState()
      const currentNode = state.nodes.find(node => node.id === originNode)
      return request === selectorTestSequence.current && state.id === originDocument && currentNode &&
        JSON.stringify([currentNode.data[id], currentNode.data.selectorHints ?? null]) === target
    }
    setTestingField(id)
    try {
      const res = await elementPickerApi.testSelector(selector, hints)
      if (!isCurrent()) {
        if (request === selectorTestSequence.current) addLog({ level: 'warning', message: '定位配置已变化，旧测试结果未应用，请重新测试。' })
        return
      }
      const d = res.data
      if (res.error || !d?.success) {
        addLog({ level: 'error', nodeId: originNode || undefined, message: `测试失败：${res.error || d?.error || '未知错误'}` })
      } else if (d.matched) {
        const via = d.isPrimary ? '' : `（经自愈候选 ${d.matchedSelector}）`
        const txt = d.element?.text ? `，首个文本：${d.element.text}` : ''
        addLog({ level: 'success', nodeId: originNode || undefined, message: `命中 ${d.count} 个元素${via}${txt}，已在页面高亮` })
      } else {
        addLog({ level: 'warning', nodeId: originNode || undefined, message: '未命中任何元素，请检查选择器或页面是否已打开到目标位置' })
      }
    } catch (e) {
      if (isCurrent()) addLog({ level: 'error', nodeId: originNode || undefined, message: `测试选择器出错：${e}` })
    } finally {
      if (request === selectorTestSequence.current) setTestingField(null)
    }
  }

  const renderSelectorInput = (id: string, label: string, placeholder: string) => {
    const rawValue = (nodeData[id] as string) || ''
    // 显示值始终去掉 xpath= 前缀
    const displayValue = rawValue.startsWith('xpath=') ? rawValue.slice(6) : rawValue
    // 类型判断：优先采用用户手动切换的偏好；否则根据值的前缀推断
    const override = selectorTypeOverride[id]
    const isXPath = override ? override === 'xpath' : rawValue.startsWith('xpath=')
    const selectorType = isXPath ? 'xpath' : 'css'

    const handleSelectorChange = (v: string) => {
      // 根据当前模式写入：XPath 模式带前缀（空值仍存空字符串，不污染数据）
      handleChange(id, isXPath ? (v ? 'xpath=' + v : '') : v)
    }

    const toggleSelectorType = () => {
      const nextType = isXPath ? 'css' : 'xpath'
      setSelectorTypeOverride((prev) => ({ ...prev, [id]: nextType }))
      // 同步重写当前值（空值时不写前缀，避免产生无效的 'xpath=' 空选择器）
      if (nextType === 'xpath') {
        handleChange(id, displayValue ? 'xpath=' + displayValue : '')
      } else {
        handleChange(id, displayValue)
      }
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor={id}>{label}</Label>
          <button
            type="button"
            onClick={toggleSelectorType}
            className="text-xs px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:text-foreground hover:border-foreground transition-colors"
            title="切换 CSS / XPath 选择器模式"
          >
            {selectorType === 'css' ? 'CSS' : 'XPath'}
          </button>
        </div>
        <div className="flex gap-2">
          <VariableInput
            value={displayValue}
            onChange={handleSelectorChange}
            placeholder={selectorType === 'xpath' ? '//div[@class="example"]' : placeholder}
            className="flex-1"
          />
          <Button
            variant="outline"
            size="icon"
            onClick={() => isPicking && pickingField === id ? stopElementPicker() : openUrlDialog(id)}
            title={isPicking && pickingField === id ? '停止选择' : '可视化选择元素'}
            disabled={isPicking && pickingField !== id}
          >
            {isPicking && pickingField === id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Crosshair className="w-4 h-4" />
            )}
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => handleTestSelector(id)}
            title="测试定位：在当前浏览器页面验证选择器是否命中并高亮"
            disabled={isPicking || testingField === id || !rawValue}
          >
            {testingField === id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ScanSearch className="w-4 h-4" />
            )}
          </Button>
        </div>
        {isPicking && pickingField === id && (
          <p className="text-xs text-blue-500">Ctrl+点击单选，Alt+点击选择相似元素</p>
        )}
      </div>
    )
  }

  // 渲染模块配置
  const renderModuleConfig = () => {
    if (excludedModuleTypes.has(nodeData.moduleType)) {
      return <div role="status">此节点已排除，保留原配置，仅供查看和导出<pre className="whitespace-pre-wrap break-all text-xs">{JSON.stringify(nodeData, null, 2)}</pre></div>
    }
    const props = { data: nodeData, onChange: handleChange, onBatchChange: handleBatchChange, renderSelectorInput }


    switch (nodeData.moduleType) {
      case 'open_page':
        return <OpenPageConfig data={nodeData} onChange={handleChange} />
      case 'dp_open_page':
        return <DpOpenPageConfig data={nodeData} onChange={handleChange} />
      case 'dp_click':
        return <DpClickConfig data={nodeData} onChange={handleChange} />
      case 'dp_input':
        return <DpInputConfig data={nodeData} onChange={handleChange} />
      case 'dp_get_text':
        return <DpGetTextConfig data={nodeData} onChange={handleChange} />
      case 'dp_get_html':
        return <DpGetHtmlConfig data={nodeData} onChange={handleChange} />
      case 'dp_run_js':
        return <DpRunJsConfig data={nodeData} onChange={handleChange} />
      case 'dp_wait_element':
        return <DpWaitElementConfig data={nodeData} onChange={handleChange} />
      case 'dp_scroll':
        return <DpScrollConfig data={nodeData} onChange={handleChange} />
      case 'dp_close':
        return <DpCloseConfig />
      case 'use_opened_page':
        return <UseOpenedPageConfig data={nodeData} onChange={handleChange} />
      case 'click_element':
        return <ClickElementConfig {...props} />
      case 'hover_element':
        return <HoverElementConfig {...props} />
      case 'input_text':
        return <InputTextConfig {...props} />
      case 'get_element_info':
        return <GetElementInfoConfig {...props} />
      case 'wait':
        return <WaitConfig {...props} />
      case 'wait_element':
        return <WaitElementConfig {...props} />
      case 'refresh_page':
        return <RefreshPageConfig data={nodeData} onChange={handleChange} />
      case 'go_back':
        return <GoBackConfig data={nodeData} onChange={handleChange} />
      case 'go_forward':
        return <GoForwardConfig data={nodeData} onChange={handleChange} />
      case 'handle_dialog':
        return <HandleDialogConfig data={nodeData} onChange={handleChange} />
      case 'inject_javascript':
        return <InjectJavaScriptConfig data={nodeData} onChange={handleChange} />
      case 'switch_iframe':
        return <SwitchIframeConfig data={nodeData} onChange={handleChange} />
      case 'switch_to_main':
        return <SwitchToMainConfig />
      case 'close_page':
        return (
          <p className="text-sm text-muted-foreground">
            关闭当前打开的网页，无需额外配置
          </p>
        )
      case 'project_manual':
      case 'project_end':
        return <ProjectLifecycleConfig key={selectedNodeId} data={nodeData} onChange={handleChange} />
      case 'project_data':
        return <ProjectDataConfig key={selectedNodeId} data={nodeData} onChange={handleChange} />
      case 'set_variable':
        return <SetVariableConfig data={nodeData} onChange={handleChange} />
      case 'increment_decrement':
        return <IncrementDecrementConfig data={nodeData} onChange={handleChange} />
      case 'print_log':
        return <PrintLogConfig data={nodeData} onChange={handleChange} />
      case 'play_sound':
        return <PlaySoundConfig data={nodeData} onChange={handleChange} />
      case 'system_notification':
        return <SystemNotificationConfig data={nodeData} onChange={handleChange} />
      case 'input_prompt':
        return <InputPromptConfig data={nodeData} onChange={handleChange} />
      case 'text_to_speech':
        return <TextToSpeechConfig data={nodeData} onChange={handleChange} />
      case 'js_script':
        return <JsScriptConfig data={nodeData} onChange={handleChange} />
      case 'python_script':
        return <PythonScriptConfig data={nodeData} onChange={handleChange} />
      case 'extract_table_data':
        return <ExtractTableDataConfig {...props} />
      case 'switch_tab':
        return <SwitchTabConfig data={nodeData} onChange={handleChange} />
      case 'select_dropdown':
        return <SelectDropdownConfig {...props} />
      case 'set_checkbox':
        return <SetCheckboxConfig {...props} />
      case 'drag_element':
        return <DragElementConfig {...props} />
      case 'scroll_page':
        return <ScrollPageConfig data={nodeData} onChange={handleChange} />
      case 'upload_file':
        return <UploadFileConfig {...props} />
      case 'download_file':
        return <DownloadFileConfig {...props} />
      case 'save_image':
        return <SaveImageConfig {...props} />
      case 'get_child_elements':
        return <GetChildElementsConfig {...props} />
      case 'get_sibling_elements':
        return <GetSiblingElementsConfig {...props} />
      case 'screenshot':
        return <ScreenshotConfig {...props} />
      case 'ocr_captcha':
        return <OCRCaptchaConfig {...props} />
      case 'slider_captcha':
        return <SliderCaptchaConfig {...props} />
      case 'send_email':
        return <SendEmailConfig data={nodeData} onChange={handleChange} />
      case 'set_clipboard':
        return <SetClipboardConfig data={nodeData} onChange={handleChange} />
      case 'get_clipboard':
        return <GetClipboardConfig data={nodeData} onChange={handleChange} />
      case 'shutdown_system':
        return <ShutdownSystemConfig data={nodeData} onChange={handleChange} />
      case 'lock_screen':
        return <LockScreenConfig />
      case 'run_command':
        return <RunCommandConfig data={nodeData} onChange={handleChange} />
      case 'element_exists':
        return <ElementExistsConfig {...props} />
      case 'element_visible':
        return <ElementVisibleConfig {...props} />
      case 'network_capture':
        return <NetworkCaptureConfig data={nodeData} onChange={handleChange} />
      case 'ai_chat':
        return <AIChatConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'ai_extract':
      case 'ai_classify':
      case 'ai_summarize':
      case 'ai_translate':
      case 'ai_sentiment':
      case 'ai_normalize':
      case 'ai_dedup_semantic':
      case 'ai_route':
        return <AITaskConfig moduleType={String(nodeData.moduleType)} data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'ai_vision':
        return <AIVisionConfig {...props} />
      case 'ai_vision_act':
        return <AIVisionActConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'ai_smart_scraper':
        return <AISmartScraperConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'ai_element_selector':
        return <AIElementSelectorConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'firecrawl_scrape':
        return <FirecrawlScrapeConfig data={nodeData} onChange={handleChange} />
      case 'firecrawl_map':
        return <FirecrawlMapConfig data={nodeData} onChange={handleChange} />
      case 'firecrawl_crawl':
        return <FirecrawlCrawlConfig data={nodeData} onChange={handleChange} />
      case 'proxy_change_ip':
      case 'proxy_change_location':
      case 'proxy_query':
        return <ProxyControlConfig data={nodeData} onChange={handleChange} />
      case 'api_request':
        return <ApiRequestConfig data={nodeData} onChange={handleChange} />
      case 'condition':
        return <ConditionConfig {...props} />
      case 'assert_checkpoint':
        return <AssertCheckpointConfig {...props} />
      case 'loop':
        return <LoopConfig data={nodeData} onChange={handleChange} />
      case 'infinite_loop':
        return <InfiniteLoopConfig data={nodeData} onChange={handleChange} />
      case 'foreach':
        return <ForeachConfig data={nodeData} onChange={handleChange} />
      case 'foreach_dict':
        return <ForeachDictConfig data={nodeData} onChange={handleChange} />
      case 'scheduled_task':
        return <ScheduledTaskConfig data={nodeData} onChange={handleChange} />
      case 'subflow':
        return <SubflowConfig data={nodeData} onChange={handleChange} />
      case 'run_workflow_file':
        return <RunWorkflowFileConfig data={nodeData} onChange={handleChange} />
      case 'break_loop':
        return (
          <p className="text-sm text-muted-foreground">
            跳出当前循环，继续执行循环后的模块
          </p>
        )
      case 'continue_loop':
        return (
          <p className="text-sm text-muted-foreground">
            跳过当前循环的剩余部分，进入下一次循环
          </p>
        )
      case 'stop_workflow':
        return (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              立即停止整个工作流的执行，不再执行后续模块
            </p>
            <div className="space-y-2">
              <Label htmlFor="stopReason">停止原因（可选）</Label>
              <Input
                id="stopReason"
                value={(nodeData.stopReason as string) || ''}
                onChange={(e) => handleChange('stopReason', e.target.value)}
                placeholder="输入停止原因，将显示在日志中"
                className="transition-all duration-200 focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              />
            </div>
          </div>
        )
      // 触发器模块
      case 'webhook_trigger':
        return <WebhookTriggerConfig data={nodeData} onChange={handleChange} />
      case 'hotkey_trigger':
        return <HotkeyTriggerConfig data={nodeData} onChange={handleChange} />
      case 'file_watcher_trigger':
        return <FileWatcherTriggerConfig data={nodeData} onChange={handleChange} />
      case 'email_trigger':
        return <EmailTriggerConfig data={nodeData} onChange={handleChange} />
      case 'api_trigger':
        return <ApiTriggerConfig data={nodeData} onChange={handleChange} />
      case 'mouse_trigger':
        return <MouseTriggerConfig data={nodeData} onChange={handleChange} />
      case 'image_trigger':
        return <ImageTriggerConfig data={nodeData} onChange={handleChange} />
      case 'sound_trigger':
        return <SoundTriggerConfig data={nodeData} onChange={handleChange} />
      case 'face_trigger':
        return <FaceTriggerConfig data={nodeData} onChange={handleChange} />
      case 'gesture_trigger':
        return <GestureTriggerConfig data={nodeData} onChange={handleChange} />
      case 'element_change_trigger':
        return <ElementChangeTriggerConfig {...props} />
      case 'regex_extract':
        return <RegexExtractConfig data={nodeData} onChange={handleChange} />
      case 'string_replace':
        return <StringReplaceConfig data={nodeData} onChange={handleChange} />
      case 'string_split':
        return <StringSplitConfig data={nodeData} onChange={handleChange} />
      case 'string_join':
        return <StringJoinConfig data={nodeData} onChange={handleChange} />
      case 'string_concat':
        return <StringConcatConfig data={nodeData} onChange={handleChange} />
      case 'string_trim':
        return <StringTrimConfig data={nodeData} onChange={handleChange} />
      case 'string_case':
        return <StringCaseConfig data={nodeData} onChange={handleChange} />
      case 'string_substring':
        return <StringSubstringConfig data={nodeData} onChange={handleChange} />
      case 'json_parse':
        return <JsonParseConfig data={nodeData} onChange={handleChange} />
      case 'base64':
        return <Base64Config data={nodeData} onChange={handleChange} />
      case 'random_number':
        return <RandomNumberConfig data={nodeData} onChange={handleChange} />
      case 'get_time':
        return <GetTimeConfig data={nodeData} onChange={handleChange} />
      case 'list_operation':
        return <ListOperationConfig data={nodeData} onChange={handleChange} />
      case 'list_get':
        return <ListGetConfig data={nodeData} onChange={handleChange} />
      case 'list_length':
        return <ListLengthConfig data={nodeData} onChange={handleChange} />
      case 'list_export':
        return <ListExportConfig data={nodeData} onChange={handleChange} />
      case 'list_sum':
        return <ListSumConfig data={nodeData} onChange={handleChange} />
      case 'list_average':
        return <ListAverageConfig data={nodeData} onChange={handleChange} />
      case 'list_max':
        return <ListMaxConfig data={nodeData} onChange={handleChange} />
      case 'list_min':
        return <ListMinConfig data={nodeData} onChange={handleChange} />
      case 'list_sort':
        return <ListSortConfig data={nodeData} onChange={handleChange} />
      case 'list_unique':
        return <ListUniqueConfig data={nodeData} onChange={handleChange} />
      case 'list_slice':
        return <ListSliceConfig data={nodeData} onChange={handleChange} />
      case 'list_reverse':
        return <ListReverseConfig data={nodeData} onChange={handleChange} />
      case 'list_find':
        return <ListFindConfig data={nodeData} onChange={handleChange} />
      case 'list_count':
        return <ListCountConfig data={nodeData} onChange={handleChange} />
      case 'list_filter':
        return <ListFilterConfig data={nodeData} onChange={handleChange} />
      case 'list_map':
        return <ListMapConfig data={nodeData} onChange={handleChange} />
      case 'list_merge':
        return <ListMergeConfig data={nodeData} onChange={handleChange} />
      case 'list_flatten':
        return <ListFlattenConfig data={nodeData} onChange={handleChange} />
      case 'list_chunk':
        return <ListChunkConfig data={nodeData} onChange={handleChange} />
      case 'list_remove_empty':
        return <ListRemoveEmptyConfig data={nodeData} onChange={handleChange} />
      case 'list_intersection':
        return <ListIntersectionConfig data={nodeData} onChange={handleChange} />
      case 'list_union':
        return <ListUnionConfig data={nodeData} onChange={handleChange} />
      case 'list_difference':
        return <ListDifferenceConfig data={nodeData} onChange={handleChange} />
      case 'list_cartesian_product':
        return <ListCartesianProductConfig data={nodeData} onChange={handleChange} />
      case 'list_shuffle':
        return <ListShuffleConfig data={nodeData} onChange={handleChange} />
      case 'list_sample':
        return <ListSampleConfig data={nodeData} onChange={handleChange} />
      case 'dict_operation':
        return <DictOperationConfig data={nodeData} onChange={handleChange} />
      case 'dict_get':
        return <DictGetConfig data={nodeData} onChange={handleChange} />
      case 'dict_keys':
        return <DictKeysConfig data={nodeData} onChange={handleChange} />
      case 'dict_merge':
        return <DictMergeConfig data={nodeData} onChange={handleChange} />
      case 'dict_filter':
        return <DictFilterConfig data={nodeData} onChange={handleChange} />
      case 'dict_map_values':
        return <DictMapValuesConfig data={nodeData} onChange={handleChange} />
      case 'dict_invert':
        return <DictInvertConfig data={nodeData} onChange={handleChange} />
      case 'dict_sort':
        return <DictSortConfig data={nodeData} onChange={handleChange} />
      case 'dict_deep_copy':
        return <DictDeepCopyConfig data={nodeData} onChange={handleChange} />
      case 'dict_get_path':
        return <DictGetPathConfig data={nodeData} onChange={handleChange} />
      case 'dict_flatten':
        return <DictFlattenConfig data={nodeData} onChange={handleChange} />
      case 'math_round':
        return <MathRoundConfig data={nodeData} onChange={handleChange} />
      case 'math_base_convert':
        return <MathBaseConvertConfig data={nodeData} onChange={handleChange} />
      case 'math_floor':
        return <MathFloorConfig data={nodeData} onChange={handleChange} />
      case 'math_modulo':
        return <MathModuloConfig data={nodeData} onChange={handleChange} />
      case 'math_abs':
        return <MathAbsConfig data={nodeData} onChange={handleChange} />
      case 'math_sqrt':
        return <MathSqrtConfig data={nodeData} onChange={handleChange} />
      case 'math_power':
        return <MathPowerConfig data={nodeData} onChange={handleChange} />
      case 'math_log':
        return <MathLogConfig data={nodeData} onChange={handleChange} />
      case 'math_trig':
        return <MathTrigConfig data={nodeData} onChange={handleChange} />
      case 'math_exp':
        return <MathExpConfig data={nodeData} onChange={handleChange} />
      case 'math_gcd':
        return <MathGcdConfig data={nodeData} onChange={handleChange} />
      case 'math_lcm':
        return <MathLcmConfig data={nodeData} onChange={handleChange} />
      case 'math_factorial':
        return <MathFactorialConfig data={nodeData} onChange={handleChange} />
      case 'math_permutation':
        return <MathPermutationConfig data={nodeData} onChange={handleChange} />
      case 'math_percentage':
        return <MathPercentageConfig data={nodeData} onChange={handleChange} />
      case 'math_clamp':
        return <MathClampConfig data={nodeData} onChange={handleChange} />
      case 'math_random_advanced':
        return <MathRandomAdvancedConfig data={nodeData} onChange={handleChange} />
      case 'stat_median':
        return <StatMedianConfig data={nodeData} onChange={handleChange} />
      case 'stat_mode':
        return <StatModeConfig data={nodeData} onChange={handleChange} />
      case 'stat_variance':
        return <StatVarianceConfig data={nodeData} onChange={handleChange} />
      case 'stat_stdev':
        return <StatStdevConfig data={nodeData} onChange={handleChange} />
      case 'stat_percentile':
        return <StatPercentileConfig data={nodeData} onChange={handleChange} />
      case 'stat_normalize':
        return <StatNormalizeConfig data={nodeData} onChange={handleChange} />
      case 'stat_standardize':
        return <StatStandardizeConfig data={nodeData} onChange={handleChange} />
      case 'csv_parse':
        return <CsvParseConfig data={nodeData} onChange={handleChange} />
      case 'csv_generate':
        return <CsvGenerateConfig data={nodeData} onChange={handleChange} />
      case 'list_to_string_advanced':
        return <ListToStringAdvancedConfig data={nodeData} onChange={handleChange} />
      case 'table_add_row':
        return <TableAddRowConfig data={nodeData} onChange={handleChange} />
      case 'table_add_column':
        return <TableAddColumnConfig data={nodeData} onChange={handleChange} />
      case 'table_set_cell':
        return <TableSetCellConfig data={nodeData} onChange={handleChange} />
      case 'table_get_cell':
        return <TableGetCellConfig data={nodeData} onChange={handleChange} />
      case 'table_delete_row':
        return <TableDeleteRowConfig data={nodeData} onChange={handleChange} />
      case 'table_clear':
        return <TableClearConfig />
      case 'table_export':
        return <TableExportConfig data={nodeData} onChange={handleChange} />
      case 'db_connect':
        return <DbConnectConfig data={nodeData} onChange={handleChange} />
      case 'db_query':
        return <DbQueryConfig data={nodeData} onChange={handleChange} />
      case 'db_execute':
        return <DbExecuteConfig data={nodeData} onChange={handleChange} />
      case 'db_insert':
        return <DbInsertConfig data={nodeData} onChange={handleChange} />
      case 'db_update':
        return <DbUpdateConfig data={nodeData} onChange={handleChange} />
      case 'db_delete':
        return <DbDeleteConfig data={nodeData} onChange={handleChange} />
      case 'db_close':
        return <DbCloseConfig data={nodeData} onChange={handleChange} />
      case 'face_recognition':
        return <FaceRecognitionConfig data={nodeData} onChange={handleChange} />
      case 'image_ocr':
        return <ImageOCRConfig data={nodeData} onChange={handleChange} />
      // 高级模块
      case 'export_log':
        return <ExportLogConfig data={nodeData} onChange={handleChange} />
      case 'share_folder':
        return <ShareFolderConfig data={nodeData} onChange={handleChange} />
      case 'share_file':
        return <ShareFileConfig data={nodeData} onChange={handleChange} />
      case 'stop_share':
        return <StopShareConfig data={nodeData} onChange={handleChange} />
      case 'start_screen_share':
        return <StartScreenShareConfig data={nodeData} onChange={handleChange} />
      case 'stop_screen_share':
        return <StopScreenShareConfig data={nodeData} onChange={handleChange} />
      case 'random_password_generator':
        return <RandomPasswordGeneratorConfig config={nodeData} updateConfig={handleChange} />
      case 'url_encode_decode':
        return <URLEncodeDecodeConfig config={nodeData} updateConfig={handleChange} />
      case 'md5_encrypt':
        return <MD5EncryptConfig config={nodeData} updateConfig={handleChange} />
      case 'sha_encrypt':
        return <SHAEncryptConfig config={nodeData} updateConfig={handleChange} />
      case 'timestamp_converter':
        return <TimestampConverterConfig config={nodeData} updateConfig={handleChange} />
      case 'rgb_to_hsv':
        return <RGBToHSVConfig config={nodeData} updateConfig={handleChange} />
      case 'rgb_to_cmyk':
        return <RGBToCMYKConfig config={nodeData} updateConfig={handleChange} />
      case 'hex_to_cmyk':
        return <HEXToCMYKConfig config={nodeData} updateConfig={handleChange} />
      case 'uuid_generator':
        return <UUIDGeneratorConfig config={nodeData} updateConfig={handleChange} />
      case 'printer_call':
        return <PrinterCallConfig config={nodeData} updateConfig={handleChange} />
      // 测试报告模块
      case 'allure_init':
        return <AllureInitConfig data={nodeData} onChange={handleChange} />
      case 'allure_start_test':
        return <AllureStartTestConfig data={nodeData} onChange={handleChange} />
      case 'allure_add_step':
        return <AllureAddStepConfig data={nodeData} onChange={handleChange} />
      case 'allure_add_attachment':
        return <AllureAddAttachmentConfig data={nodeData} onChange={handleChange} />
      case 'allure_stop_test':
        return <AllureStopTestConfig data={nodeData} onChange={handleChange} />
      case 'allure_generate_report':
        return <AllureGenerateReportConfig data={nodeData} onChange={handleChange} />
      // Apprise多渠道通知模块
      case 'notify_discord':
        return <NotifyDiscordConfig data={nodeData} onChange={handleChange} />
      case 'notify_telegram':
        return <NotifyTelegramConfig data={nodeData} onChange={handleChange} />
      case 'notify_dingtalk':
        return <NotifyDingTalkConfig data={nodeData} onChange={handleChange} />
      case 'notify_wecom':
        return <NotifyWeComConfig data={nodeData} onChange={handleChange} />
      case 'notify_bark':
        return <NotifyBarkConfig data={nodeData} onChange={handleChange} />
      case 'notify_slack':
        return <NotifySlackConfig data={nodeData} onChange={handleChange} />
      case 'notify_msteams':
        return <NotifyMSTeamsConfig data={nodeData} onChange={handleChange} />
      case 'notify_pushover':
        return <NotifyPushoverConfig data={nodeData} onChange={handleChange} />
      case 'notify_pushbullet':
        return <NotifyPushBulletConfig data={nodeData} onChange={handleChange} />
      case 'notify_gotify':
        return <NotifyGotifyConfig data={nodeData} onChange={handleChange} />
      case 'notify_serverchan':
        return <NotifyServerChanConfig data={nodeData} onChange={handleChange} />
      case 'notify_pushplus':
        return <NotifyPushPlusConfig data={nodeData} onChange={handleChange} />
      case 'notify_webhook':
        return <NotifyWebhookConfig data={nodeData} onChange={handleChange} />
      case 'notify_ntfy':
        return <NotifyNtfyConfig data={nodeData} onChange={handleChange} />
      case 'notify_matrix':
        return <NotifyMatrixConfig data={nodeData} onChange={handleChange} />
      case 'notify_rocketchat':
        return <NotifyRocketChatConfig data={nodeData} onChange={handleChange} />
      
      // Webhook请求模块
      case 'webhook_request':
        return <WebhookRequestConfig data={nodeData} onChange={handleChange} />
      
      // Oracle数据库模块
      case 'oracle_connect':
        return <OracleConnectConfig data={nodeData} onChange={handleChange} />
      case 'oracle_query':
        return <OracleQueryConfig data={nodeData} onChange={handleChange} />
      case 'oracle_execute':
        return <OracleExecuteConfig data={nodeData} onChange={handleChange} />
      case 'oracle_insert':
        return <OracleInsertConfig data={nodeData} onChange={handleChange} />
      case 'oracle_update':
        return <OracleUpdateConfig data={nodeData} onChange={handleChange} />
      case 'oracle_delete':
        return <OracleDeleteConfig data={nodeData} onChange={handleChange} />
      
      // PostgreSQL数据库模块
      case 'postgresql_connect':
        return <PostgreSQLConnectConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_query':
        return <PostgreSQLQueryConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_execute':
        return <PostgreSQLExecuteConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_insert':
        return <PostgreSQLInsertConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_update':
        return <PostgreSQLUpdateConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_delete':
        return <PostgreSQLDeleteConfig data={nodeData} onChange={handleChange} />
      
      // MongoDB数据库模块
      case 'mongodb_connect':
        return <MongoDBConnectConfig data={nodeData} onChange={handleChange} />
      case 'mongodb_find':
        return <MongoDBFindConfig data={nodeData} onChange={handleChange} />
      case 'mongodb_insert':
        return <MongoDBInsertConfig data={nodeData} onChange={handleChange} />
      case 'mongodb_update':
        return <MongoDBUpdateConfig data={nodeData} onChange={handleChange} />
      case 'mongodb_delete':
        return <MongoDBDeleteConfig data={nodeData} onChange={handleChange} />
      
      // SQL Server数据库模块
      case 'sqlserver_connect':
        return <SQLServerConnectConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_query':
        return <SQLServerQueryConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_execute':
        return <SQLServerExecuteConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_insert':
        return <SQLServerInsertConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_update':
        return <SQLServerUpdateConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_delete':
        return <SQLServerDeleteConfig data={nodeData} onChange={handleChange} />
      
      // SQLite数据库模块
      case 'sqlite_connect':
        return <SQLiteConnectConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_query':
        return <SQLiteQueryConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_execute':
        return <SQLiteExecuteConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_insert':
        return <SQLiteInsertConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_update':
        return <SQLiteUpdateConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_delete':
        return <SQLiteDeleteConfig data={nodeData} onChange={handleChange} />
      
      // Redis数据库模块
      case 'redis_connect':
        return <RedisConnectConfig data={nodeData} onChange={handleChange} />
      case 'redis_get':
        return <RedisGetConfig data={nodeData} onChange={handleChange} />
      case 'redis_set':
        return <RedisSetConfig data={nodeData} onChange={handleChange} />
      case 'redis_del':
        return <RedisDelConfig data={nodeData} onChange={handleChange} />
      case 'redis_hget':
        return <RedisHGetConfig data={nodeData} onChange={handleChange} />
      case 'redis_hset':
        return <RedisHSetConfig data={nodeData} onChange={handleChange} />
      
      // 数据库断开连接模块
      case 'oracle_disconnect':
        return <OracleDisconnectConfig data={nodeData} onChange={handleChange} />
      case 'postgresql_disconnect':
        return <PostgreSQLDisconnectConfig data={nodeData} onChange={handleChange} />
      case 'mongodb_disconnect':
        return <MongoDBDisconnectConfig data={nodeData} onChange={handleChange} />
      case 'sqlserver_disconnect':
        return <SQLServerDisconnectConfig data={nodeData} onChange={handleChange} />
      case 'sqlite_disconnect':
        return <SQLiteDisconnectConfig data={nodeData} onChange={handleChange} />
      case 'redis_disconnect':
        return <RedisDisconnectConfig data={nodeData} onChange={handleChange} />
      
      // SSH远程操作模块
      case 'ssh_connect':
        return <SSHConnectConfig data={nodeData} onChange={handleChange} />
      case 'ssh_execute_command':
        return <SSHExecuteCommandConfig data={nodeData} onChange={handleChange} />
      case 'ssh_upload_file':
        return <SSHUploadFileConfig data={nodeData} onChange={handleChange} />
      case 'ssh_download_file':
        return <SSHDownloadFileConfig data={nodeData} onChange={handleChange} />
      case 'ssh_disconnect':
        return <SSHDisconnectConfig data={nodeData} onChange={handleChange} />
      // 自定义模块
      case 'custom_module':
        return <CustomModuleConfig data={nodeData} onChange={handleChange} />
      
      // AI生图生视频模块
      case 'ai_generate_image':
        return <AIGenerateImageConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      case 'ai_generate_video':
        return <AIGenerateVideoConfig data={nodeData} onChange={handleChange} onBatchChange={handleBatchChange} />
      
      // 概率触发器模块
      case 'probability_trigger':
        return <ProbabilityTriggerConfig data={nodeData} onChange={handleChange} />
      
      // 网络监听模块
      case 'network_monitor_start':
        return <NetworkMonitorStartConfig data={nodeData} onChange={handleChange} />
      case 'network_monitor_wait':
        return <NetworkMonitorWaitConfig data={nodeData} onChange={handleChange} />
      case 'network_monitor_stop':
        return <NetworkMonitorStopConfig data={nodeData} onChange={handleChange} />
      
      case 'wait_page_load':
        return <WaitPageLoadConfig data={nodeData} onChange={handleChange} />
      case 'page_load_complete':
        return <PageLoadCompleteConfig data={nodeData} onChange={handleChange} />
      case 'group':
        return <GroupConfig data={nodeData} onChange={handleChange} />
      case 'subflow_header':
        return <SubflowHeaderConfig data={nodeData} onChange={handleChange} />
      case 'note':
        return (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              便签模块用于在画布上添加注释，不会被执行
            </p>
            <div className="space-y-2">
              <Label htmlFor="noteContent">便签内容</Label>
              <textarea
                id="noteContent"
                value={(nodeData.content as string) || ''}
                onChange={(e) => handleChange('content', e.target.value)}
                placeholder="在这里输入便签内容..."
                className="w-full min-h-[100px] px-3 py-2 text-sm border rounded-md resize-y"
              />
            </div>
          </div>
        )
      default:
        return (
          <p className="text-sm text-muted-foreground">
            该模块暂无额外配置
          </p>
        )
    }
  }

  return (
    <>
      {/* URL输入对话框 */}
      <UrlInputDialog
        isOpen={showUrlDialog}
        url={pickerUrl}
        onUrlChange={setPickerUrl}
        onClose={() => setShowUrlDialog(false)}
        onConfirm={() => pendingField && startElementPicker(pendingField, pickerUrl)}
      />
      
      {/* 相似元素选择对话框 */}
      {similarResult && (
        <SimilarSelectorDialog
          isOpen={showSimilarDialog}
          onClose={() => {
            setShowSimilarDialog(false)
            setSimilarResult(null)
            stopElementPicker()
          }}
          onConfirm={handleSimilarConfirm}
          pattern={similarResult.pattern}
          count={similarResult.count}
          minIndex={similarResult.minIndex}
          maxIndex={similarResult.maxIndex}
        />
      )}
      
      <aside
        className="relative border-l border-[hsl(var(--border))] bg-[hsl(var(--card))] flex flex-col"
        style={{
          width: isCollapsed ? 48 : effectiveRightWidth,
          transition: draftRightWidth === null ? 'width 200ms ease-out' : 'none',
        }}
      >
        {isCollapsed ? (
          <button
            type="button"
            className="flex flex-col items-center py-3 gap-2.5 hover:bg-[hsl(var(--brand-50))] transition-colors h-full w-full"
            onClick={() => setIsCollapsed(false)}
            title="展开配置面板"
          >
            <span className="flex items-center justify-center w-8 h-8 rounded-control bg-gradient-to-br from-[hsl(var(--brand-500))] to-[hsl(var(--brand-700))] text-white shadow-brand-glow">
              <ChevronLeft className="w-4 h-4" />
            </span>
            <span className="icon-chip icon-chip-brand !w-7 !h-7">
              {(() => {
                const MIcon = moduleIcons[nodeData.moduleType as keyof typeof moduleIcons] || Settings
                return <MIcon className="w-3.5 h-3.5" />
              })()}
            </span>
            <span className="text-[10px] text-[hsl(var(--brand-700))] font-semibold mt-1 tracking-wide" style={{ writingMode: 'vertical-rl' }}>
              {String(moduleTypeLabels[nodeData.moduleType as keyof typeof moduleTypeLabels] ?? nodeData.moduleType)}
            </span>
          </button>
        ) : (
          <>
            <div
              className="p-3.5 border-b border-[hsl(var(--border))] flex items-center justify-between"
              style={{ background: 'linear-gradient(180deg, hsl(var(--brand-50) / 0.5), hsl(var(--card)))' }}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="icon-block icon-block-brand !w-9 !h-9 !rounded-card flex-shrink-0">
                  {(() => {
                    const MIcon = moduleIcons[nodeData.moduleType as keyof typeof moduleIcons] || Settings
                    return <MIcon className="w-4 h-4" strokeWidth={2.4} />
                  })()}
                </div>
                <div className="min-w-0">
                  <h2 className="text-[14px] font-bold text-[hsl(var(--slate-900))] truncate tracking-tight">{String(moduleTypeLabels[nodeData.moduleType as keyof typeof moduleTypeLabels] ?? nodeData.moduleType)}</h2>
                  <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-0.5 flex items-center gap-1.5">
                    <span className="badge badge-brand !py-0 !text-[9.5px]">{String(nodeData.moduleType)}</span>
                    {Boolean(nodeData.disabled) && <span className="badge badge-warning !py-0 !text-[9.5px]">已禁用</span>}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="tonal"
                  size="icon-sm"
                  onClick={askAIAboutNode}
                  title="问 AI（解释 / 优化 / 修复此模块）"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant={nodeData.disabled ? 'tonal-warning' : 'tonal'}
                  size="icon-sm"
                  onClick={() => {
                    toggleNodesDisabled([selectedNode.id])
                    addLog({ level: 'info', message: nodeData.disabled ? '已启用模块' : '已禁用模块' })
                  }}
                  title={nodeData.disabled ? '启用模块 (Ctrl+D)' : '禁用模块 (Ctrl+D)'}
                >
                  <Ban className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="tonal-danger"
                  size="icon-sm"
                  onClick={handleDelete}
                  title="删除模块"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setIsCollapsed(true)}
                  title="收起配置面板"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div key={`${documentId}:${selectedNodeId}`} className="space-y-4 animate-fade-in">
                {/* 必填校验提示 */}
                {(() => {
                  if (requiredFields.loading) return <p role="status" className="text-xs text-muted-foreground">正在读取必填字段规则…</p>
                  if (requiredFields.error) return <div role="alert" className="text-xs text-[hsl(var(--danger-600))]">
                    <p>必填字段规则未加载：{requiredFields.error}</p>
                    <Button size="sm" variant="outline" onClick={requiredFields.retry}>重新读取字段规则</Button>
                  </div>
                  if (!requiredFields.data?.coveredModules.includes(String(nodeData.moduleType))) return <p className="text-xs text-muted-foreground">此节点尚未提供必填字段规则，请核对配置。</p>
                  const missing = getMissingRequiredLabels(String(nodeData.moduleType), nodeData as Record<string, unknown>, requiredFields.data.requiredFields, requiredFields.data)
                  if (missing.length === 0) return null
                  return (
                    <div className="flex items-start gap-2 px-3 py-2 rounded-control bg-[hsl(var(--warning-50))] border border-[hsl(var(--warning-500)/0.3)] text-[hsl(var(--warning-700))]">
                      <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-[hsl(var(--warning-500))] text-white flex items-center justify-center text-[10px] font-bold">!</span>
                      <div className="text-[12px] leading-relaxed">
                        <span className="font-semibold">有 {missing.length} 个必填项未填写：</span>
                        <span>
                          {missing.map((label, i) => (
                            <span key={i}>{i > 0 ? '、' : ''}{label}</span>
                          ))}
                        </span>
                        <div className="text-[11px] text-[hsl(var(--warning-600))] mt-0.5">未填写可能导致该模块执行失败</div>
                      </div>
                    </div>
                  )
                })()}

                {/* 通用配置 */}
                <div className="space-y-2">
                  <Label htmlFor="name">节点备注</Label>
                  <Input
                    id="name"
                    value={(nodeData.name as string) || ''}
                    onChange={(e) => handleChange('name', e.target.value)}
                    placeholder="可选的节点备注"
                    className="transition-all duration-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                {/* 模块特定配置 */}
                {renderModuleConfig()}

                {/* 错误处理（错误回流 / 重试 / 跳过）——与模块条视图共用同一份 errorPolicy */}
                {(() => {
                  const pol: ErrorPolicy = (nodeData.errorPolicy as ErrorPolicy) || { mode: 'stop', maxRetries: 1, interval: 0, onExhausted: 'stop' }
                  const setPol = (patch: Partial<ErrorPolicy>) => {
                    const next: ErrorPolicy = { maxRetries: 1, interval: 0, onExhausted: 'stop', ...pol, ...patch }
                    handleChange('errorPolicy', next.mode === 'stop' ? undefined : next)
                  }
                  const cands = nodes
                    .filter((n) => n.type === 'moduleNode' && n.id !== selectedNodeId)
                    .map((n) => ({ id: n.id, label: (n.data?.label as string) || moduleTypeLabels[n.data?.moduleType as keyof typeof moduleTypeLabels] || n.id }))
                  return (
                    <div className="pt-4 border-t space-y-3">
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">错误处理</h3>
                      <div className="space-y-2">
                        <Label>出错时</Label>
                        <Select value={pol.mode} onChange={(e) => setPol({ mode: e.target.value as ErrorPolicy['mode'] })}>
                          <option value="stop">失败即停（默认）</option>
                          <option value="continue">跳过并继续</option>
                          <option value="retry-self">原地重试当前模块</option>
                          <option value="retry-from">回流到上层模块重试</option>
                        </Select>
                      </div>
                      {(pol.mode === 'retry-self' || pol.mode === 'retry-from') && (
                        <>
                          {pol.mode === 'retry-from' && (
                            <div className="space-y-2">
                              <Label>回流目标模块</Label>
                              <Select value={pol.targetId || ''} placeholder="选择目标模块…" onChange={(e) => setPol({ targetId: e.target.value })}>
                                {cands.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                              </Select>
                            </div>
                          )}
                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-2">
                              <Label>重试次数</Label>
                              <NumberInput value={pol.maxRetries ?? 1} onChange={(v) => setPol({ maxRetries: v })} min={1} />
                            </div>
                            <div className="space-y-2">
                              <Label>间隔(秒)</Label>
                              <NumberInput value={pol.interval ?? 0} onChange={(v) => setPol({ interval: v })} min={0} />
                            </div>
                          </div>
                          {pol.mode === 'retry-from' && (
                            <div className="space-y-2">
                              <Label>重试用尽后</Label>
                              <Select value={pol.onExhausted || 'stop'} onChange={(e) => setPol({ onExhausted: e.target.value as 'stop' | 'continue' })}>
                                <option value="stop">停止流程</option>
                                <option value="continue">继续往下</option>
                              </Select>
                            </div>
                          )}
                        </>
                      )}
                      <p className="text-xs text-muted-foreground">
                        {pol.mode === 'retry-from'
                          ? '出错时回到所选模块，从那里重新往下执行；画布上会显示一条红色回流连线。'
                          : pol.mode === 'retry-self'
                            ? '出错时原地重跑当前模块，达到次数仍失败则停止。'
                            : pol.mode === 'continue'
                              ? '出错时记一条警告并继续执行后续模块。'
                              : '默认：该模块出错时立即停止流程。'}
                      </p>
                    </div>
                  )
                })()}

                {/* 高级配置 */}
                <div className="pt-4 border-t space-y-4">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    高级配置
                  </h3>
                  <div className="space-y-2">
                    <Label htmlFor="timeout">超时时间 (秒)</Label>
                    <NumberInput
                      id="timeout"
                      value={(nodeData.timeout as number) ?? getModuleDefaultTimeout(nodeData.moduleType as import('../types/index').ModuleType)}
                      onChange={(v) => handleChange('timeout', v)}
                      defaultValue={getModuleDefaultTimeout(nodeData.moduleType as import('../types/index').ModuleType)}
                      min={0}
                    />
                    <p className="text-xs text-muted-foreground">
                      0 表示不限制超时，当前模块建议: {(getModuleDefaultTimeout(nodeData.moduleType as import('../types/index').ModuleType) / 1000).toFixed(0)}秒
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="timeoutAction">运行超时后</Label>
                    <Select
                      id="timeoutAction"
                      value={(nodeData.timeoutAction as string) || 'retry'}
                      onChange={(e) => handleChange('timeoutAction', e.target.value)}
                    >
                      <option value="retry">重试</option>
                      <option value="skip">跳过该模块，继续执行</option>
                      <option value="stop">停止工作流执行</option>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {(nodeData.timeoutAction as string) === 'skip' 
                        ? '超时后跳过此模块，直接执行后续流程'
                        : (nodeData.timeoutAction as string) === 'stop'
                        ? '超时后立即停止整个工作流执行'
                        : '超时后按重试次数进行重试'}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="retryCount">重试次数</Label>
                    <NumberInput
                      id="retryCount"
                      value={(nodeData.retryCount as number) ?? 0}
                      onChange={(v) => handleChange('retryCount', v)}
                      defaultValue={0}
                      min={0}
                      max={10}
                    />
                  </div>
                  {((nodeData.retryCount as number) ?? 0) > 0 && (
                    <div className="space-y-2">
                      <Label htmlFor="retryExhaustedAction">重试耗尽后</Label>
                      <Select
                        id="retryExhaustedAction"
                        value={(nodeData.retryExhaustedAction as string) || 'stop'}
                        onChange={(e) => handleChange('retryExhaustedAction', e.target.value)}
                      >
                        <option value="stop">停止工作流</option>
                        <option value="skip">跳过该模块，继续执行</option>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {(nodeData.retryExhaustedAction as string) === 'skip' 
                          ? '重试次数用完后跳过此模块，继续执行后续流程'
                          : '重试次数用完后停止整个工作流'}
                      </p>
                    </div>
                  )}
                  {((nodeData.retryCount as number) ?? 0) > 0 && (
                    <div className="space-y-2">
                      <Label htmlFor="retryDelay">重试间隔（秒）</Label>
                      <NumberInput
                        id="retryDelay"
                        value={(nodeData.retryDelay as number) ?? 0}
                        onChange={(v) => handleChange('retryDelay', v)}
                        defaultValue={0}
                        min={0}
                      />
                      <p className="text-xs text-muted-foreground">
                        每次重试前的等待时间，0 表示立即重试，可缓解被限流/页面未就绪。
                      </p>
                    </div>
                  )}
                  {((nodeData.retryCount as number) ?? 0) > 0 && ((nodeData.retryDelay as number) ?? 0) > 0 && (
                    <div className="space-y-2">
                      <Label htmlFor="retryBackoff">退避策略</Label>
                      <Select
                        id="retryBackoff"
                        value={(nodeData.retryBackoff as string) || 'fixed'}
                        onChange={(e) => handleChange('retryBackoff', e.target.value)}
                      >
                        <option value="fixed">固定间隔</option>
                        <option value="exponential">指数退避（间隔翻倍）</option>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {(nodeData.retryBackoff as string) === 'exponential'
                          ? '间隔随重试次数翻倍（如 2s → 4s → 8s），适合外部接口限流'
                          : '每次重试都等待相同时间'}
                      </p>
                    </div>
                  )}
                </div>

                {/* 变量使用提示 */}
                <div className="pt-4 border-t">
                  <div className="bg-[hsl(var(--card))] p-3 rounded-xl border border-blue-200/30 shadow-sm">
                    <p className="text-xs text-muted-foreground">
                      提示：在任意输入框中使用 <code className="bg-[hsl(var(--card))] px-1.5 py-0.5 rounded text-blue-600 font-mono">{'{变量名}'}</code> 来引用变量值
                    </p>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </>
        )}
        {!isCollapsed && (
          <PanelResizer
            direction="horizontal"
            side="left"
            size={effectiveRightWidth}
            minSize={LAYOUT_LIMITS.right.min}
            maxSize={LAYOUT_LIMITS.right.max}
            factor={-1}
            onLive={(w) => setDraftRightWidth(w)}
            onCommit={(w) => {
              setRightWidth(w)
              setDraftRightWidth(null)
            }}
          />
        )}
      </aside>
    </>
  )
}
