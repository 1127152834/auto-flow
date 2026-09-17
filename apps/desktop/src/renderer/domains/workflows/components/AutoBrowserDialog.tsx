import { getStudioTransportRevision } from '../api/transport'
// Source: WebRPA@5ccb900e, components/workflow/AutoBrowserDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useEffect, useRef } from 'react'
import { X, Globe, MousePointer, Copy, Check, RefreshCw } from 'lucide-react'
import { Button } from './controls/button'
import { BrowserProfileSelect } from './BrowserProfileSelect'
import { BrowserPagesPanel } from './BrowserPagesPanel'
import { browserApi, elementPickerApi, systemApi, featurePackApi } from '../api'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { DialogPortal } from './controls/dialog-portal'
import { MissingPacksDialog, type MissingPackGroup } from './MissingPacksDialog'
import { FeaturePackDialog } from './FeaturePackDialog'
import { requestSessionTransition } from '../lib/documentLeave'

interface AutoBrowserDialogProps {
  isOpen: boolean
  onClose: () => void
  onLog: (level: 'info' | 'success' | 'warning' | 'error', message: string) => void
}

export function AutoBrowserDialog({ isOpen, onClose, onLog }: AutoBrowserDialogProps) {
  const [browserOpen, setBrowserOpen] = useState(false)
  const [pickerActive, setPickerActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [url, setUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [lastSelector, setLastSelector] = useState('')
  const statusRequest = useRef(0)
  const commandPending = useRef(false)
  const beginCommand = () => {
    if (commandPending.current) return false
    commandPending.current = true
    statusRequest.current += 1
    setLoading(true)
    return true
  }
  const endCommand = () => { commandPending.current = false; setLoading(false) }
  const onLogRef = useRef(onLog)
  useEffect(() => { onLogRef.current = onLog }, [onLog])
  // 记录上一次已处理的选择器，避免轮询期间对同一结果重复复制/记日志
  const lastHandledRef = useRef('')
  // 打开浏览器因缺功能模块包而失败时，用这两个状态把安装引导弹出来
  const [missingPacks, setMissingPacks] = useState<MissingPackGroup[] | null>(null)
  const [showFeaturePacks, setShowFeaturePacks] = useState(false)
  // Status failures preserve the last confirmed browser state; they do not prove closure.
  const checkStatus = async () => {
    if (commandPending.current) return
    const request = ++statusRequest.current
    try {
      const result = await browserApi.getStatus()
      if (request !== statusRequest.current) return
      if (result.error) {
        onLogRef.current('error', `读取浏览器状态失败: ${result.error}`)
      } else if (result.data) {
        setBrowserOpen(result.data.isOpen)
        setPickerActive(result.data.pickerActive)
      }
    } catch (error) {
      if (request === statusRequest.current) onLogRef.current('error', `读取浏览器状态失败: ${error}`)
    }
  }

  useEffect(() => {
    if (isOpen) void checkStatus()
    return () => { statusRequest.current += 1 }
  }, [isOpen])

  // One polling request at a time; a hidden/unmounted panel must not copy late results.
  useEffect(() => {
    if (!pickerActive || !isOpen || loading) return
    let cancelled = false
    let pending = false
    let reportedError = false
    lastHandledRef.current = ''
    const timer = setInterval(async () => {
      if (pending) return
      pending = true
      try {
        const autoCopy = useGlobalConfigStore.getState().config.browser?.autoCopySelector !== false
        const singleResult = await elementPickerApi.getSelected()
        if (cancelled) return
        if (singleResult.error) throw new Error(singleResult.error)
        if (singleResult.data?.active === false) {
          setPickerActive(false)
          return
        }
        if (singleResult.data?.selected && singleResult.data.element) {
          const selector = singleResult.data.element.selector
          if (selector && selector !== lastHandledRef.current) {
            lastHandledRef.current = selector
            setLastSelector(selector)
            onLogRef.current('success', `已选择元素: ${selector}`)
            if (autoCopy) await autoCopySelector(selector, () => !cancelled)
          }
        }
        if (cancelled) return
        const similarResult = await elementPickerApi.getSimilar()
        if (cancelled) return
        if (similarResult.error) throw new Error(similarResult.error)
        if (similarResult.data?.selected && similarResult.data.similar) {
          const pattern = similarResult.data.similar.pattern
          const count = similarResult.data.similar.count
          if (pattern && pattern !== lastHandledRef.current) {
            lastHandledRef.current = pattern
            setLastSelector(pattern)
            onLogRef.current('success', `已选择 ${count} 个相似元素: ${pattern}`)
            if (autoCopy) await autoCopySelector(pattern, () => !cancelled)
          }
        }
        reportedError = false
      } catch (error) {
        if (!cancelled && !reportedError) onLogRef.current('error', `读取拾取结果失败: ${error}`)
        reportedError = true
      } finally { pending = false }
    }, 500)
    return () => { cancelled = true; clearInterval(timer) }
  }, [pickerActive, isOpen, loading])

  // 自动复制选择器：改由后端写系统剪贴板（焦点无关）。
  // 拾取元素时焦点在自动化浏览器窗口，编辑器失焦，navigator.clipboard 会以
  // "document is not focused" 拒绝复制，故这里走后端 pyperclip/win32 写入。
  const autoCopySelector = async (text: string, isCurrent: () => boolean) => {
    try {
      const res = await systemApi.setClipboard(text)
      if (!isCurrent()) return
      if (res.error) {
        onLogRef.current('warning', `选择器复制到剪贴板失败: ${res.error}`)
        return
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      onLogRef.current('success', '选择器已复制到剪贴板')
    } catch (e) {
      if (!isCurrent()) return
      onLogRef.current('warning', `选择器复制到剪贴板失败: ${e instanceof Error ? e.message : e}`)
    }
  }

  const copyToClipboard = async (text: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text)
      } else {
        const textArea = document.createElement('textarea')
        textArea.value = text
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        textArea.remove()
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      onLog('success', '已复制到剪贴板')
    } catch {
      onLog('error', '复制失败')
    }
  }

  /**
   * 打开浏览器失败时，判断是不是「缺少功能模块包」，若是则弹出安装引导。
   *
   * 后端在缺包时返回的是一段人类可读的错误（如「网页自动化功能不可用：未安装
   * Playwright。请安装「网页自动化」功能模块包后重试。」），并没有结构化标记，
   * 所以这里按关键字识别，再用与「运行前预检」同一个接口拿到准确的缺失清单，
   * 复用同一个弹窗，保证提示内容和运行前一致（含体积、备选包、安装教学）。
   */
  const maybePromptMissingPacks = async (rawError: string) => {
    const text = String(rawError || '')
    const looksMissingPack = /功能模块包|Playwright|功能不可用|未安装/.test(text)
    if (!looksMissingPack) return
    try {
      // open_page 是「网页自动化」包的代表模块，用它反查缺失的包
      const pf = await featurePackApi.preflight(['open_page'])
      if (pf.success && pf.data && pf.data.ok === false && (pf.data.missing?.length ?? 0) > 0) {
        setMissingPacks(pf.data.missing as MissingPackGroup[])
        return
      }
      // 预检说不缺包，但浏览器确实起不来：典型是功能包装过但 Playwright 内核
      // 不完整/被杀软清理。此时不能静默——否则底栏只剩一行「未安装 Playwright」，
      // 用户按提示去装却发现"已安装"，彻底卡死。
      onLog('warning', '功能包检测显示「网页自动化」已安装，但浏览器仍无法启动，可能是安装不完整或文件被清理。请在 更多 → 功能模块包 中重新安装该功能包，并重启后端服务')
      setShowFeaturePacks(true)
    } catch {
      // 预检本身失败就不再打扰用户，底栏已有明确错误信息
    }
  }

  const handleOpenBrowser = async () => {
    if (!beginCommand()) return
    try {
      const result = await browserApi.open(url || undefined, undefined, useGlobalConfigStore.getState().config.browserProfileId)
      if (result.error) {
        onLog('error', `打开浏览器失败: ${result.error}`)
        // 失败原因是「缺少功能模块包」时，直接把安装弹窗顶上来。
        // 过去只在底栏留一行「未安装 Playwright，请安装功能模块包后重试」，
        // 用户看到提示却没有任何入口，只能自己去菜单里翻。
        await maybePromptMissingPacks(result.error)
      } else {
        statusRequest.current += 1
        setBrowserOpen(true)
        onLog('success', 'CloakBrowser 会话已打开，启动参数来自管理端配置')
      }
    } catch (error) {
      onLog('error', `打开浏览器异常: ${error}`)
      await maybePromptMissingPacks(String(error))
    } finally {
      endCommand()
    }
  }

  const handleCloseBrowser = async () => {
    if (!beginCommand()) return
    const connection = getStudioTransportRevision()
    try {
      if (!await requestSessionTransition(true)) return
      if (connection !== getStudioTransportRevision()) {
        onLog('error', '服务连接已变更，未关闭新工作区的浏览器')
        return
      }
      const result = await browserApi.close()
      if (result.error) { onLog('error', `关闭浏览器失败: ${result.error}`); return }
      statusRequest.current += 1
      setBrowserOpen(false)
      setPickerActive(false)
      onLog('info', '浏览器已关闭')
    } catch (error) {
      onLog('error', `关闭浏览器失败: ${error}`)
    } finally {
      endCommand()
    }
  }

  const handleStartPicker = async () => {
    if (!beginCommand()) return
    try {
      const result = await browserApi.startPicker()
      if (result.error) {
        if (result.outcomeUnknown) setPickerActive(true)
        onLog('error', `启动选择器失败: ${result.error}`)
      } else {
        statusRequest.current += 1
        setPickerActive(true)
        onLog('info', '元素选择器已启动 - Ctrl+点击选择单个元素，Alt+点击选择相似元素')
      }
    } catch (error) {
      onLog('error', `启动选择器异常: ${error}`)
    } finally { endCommand() }
  }

  const handleStopPicker = async () => {
    if (!beginCommand()) return
    try {
      const result = await browserApi.stopPicker()
      if (result.error) { onLog('error', `停止选择器失败: ${result.error}`); return }
      statusRequest.current += 1
      setPickerActive(false)
      onLog('info', '元素选择器已停止')
    } catch (error) {
      onLog('error', `停止选择器失败: ${error}`)
    } finally { endCommand() }
  }

  if (!isOpen) return null

  return (
    <DialogPortal>
    <div
      className="fixed inset-0 flex items-center justify-center bg-[hsl(217_45%_15%_/_0.55)] backdrop-blur-[3px] animate-fade-in p-4"
      style={{ zIndex: 2147483646 }}
      onClick={onClose}
    >
      <div
        className="modern-dialog w-full max-w-[520px] max-h-[90vh] flex flex-col animate-scale-in-bounce"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="modern-dialog-header">
          <div className="modern-dialog-header-icon modern-dialog-header-icon-success">
            <Globe className="w-5 h-5" strokeWidth={2.2} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="modern-dialog-title flex items-center gap-2">
              自动化浏览器
              {browserOpen && (
                <span className="badge badge-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--success-500))] animate-pulse" />
                  已打开
                </span>
              )}
            </h3>
            <div className="modern-dialog-subtitle">登录账号、抓取选择器一站式</div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-control text-[hsl(var(--slate-500))] hover:bg-[hsl(var(--danger-50))] hover:text-[hsl(var(--danger-600))] hover:border-[hsl(var(--danger-500)/0.3)] border border-transparent transition-all duration-150 active:scale-90"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* 说明 */}
          <div className="section-block">
            <div className="section-block-header">
              <div className="icon-chip icon-chip-info !w-6 !h-6">
                <Globe className="w-3.5 h-3.5" />
              </div>
              功能说明
            </div>
            <div className="section-block-body !py-3">
              <ul className="space-y-1.5 text-[12px] text-[hsl(var(--slate-700))]">
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>使用管理端 CloakBrowser 配置；此临时会话的登录状态不会传给独立运行</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>支持元素选择器，选中后自动复制到剪贴板</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>相似元素自动用 <code className="variable-tag">{'{index}'}</code> 替换变化部分</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--violet-600))] mt-0.5 font-bold">★</span>
                  <span className="font-semibold text-[hsl(var(--violet-700))]">
                    按 <kbd className="px-1.5 py-0.5 bg-[hsl(var(--violet-100))] border border-[hsl(var(--violet-500)/0.3)] rounded text-[10px] font-mono shadow-xs">Alt+X</kbd> 使用高级元素选择器（推荐）
                  </span>
                </li>
              </ul>
            </div>
          </div>

          {/* URL 输入 - 仅在浏览器打开后显示 */}
          {browserOpen && (
            <>
              {/* Alt+X 快捷键卡 */}
              <div className="relative p-4 rounded-card border-[1.5px] border-[hsl(var(--violet-500)/0.3)] bg-gradient-to-br from-[hsl(var(--violet-50))] to-[hsl(var(--card))] overflow-hidden">
                <div className="flex items-start gap-3">
                  <div className="icon-block icon-block-violet !w-9 !h-9">
                    <MousePointer className="w-4.5 h-4.5" strokeWidth={2.2} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-bold text-[hsl(var(--violet-700))] mb-1">高级元素选择器</p>
                    <p className="text-[11.5px] text-[hsl(var(--violet-700))] mb-2 leading-relaxed">
                      在浏览器中按 <kbd className="px-2 py-0.5 bg-[hsl(var(--card))] border-[1.5px] border-[hsl(var(--violet-500)/0.4)] rounded text-[11px] font-bold text-[hsl(var(--violet-700))] shadow-soft">Alt+X</kbd> 激活智能元素定位助手
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="badge !bg-[hsl(var(--violet-100))] !text-[hsl(var(--violet-700))] !border-[hsl(var(--violet-500)/0.3)]">智能选择器生成</span>
                      <span className="badge !bg-[hsl(var(--violet-100))] !text-[hsl(var(--violet-700))] !border-[hsl(var(--violet-500)/0.3)]">批量收集管理</span>
                      <span className="badge !bg-[hsl(var(--violet-100))] !text-[hsl(var(--violet-700))] !border-[hsl(var(--violet-500)/0.3)]">可拖拽面板</span>
                    </div>
                  </div>
                </div>
              </div>

              <BrowserPagesPanel url={url} onUrlChange={setUrl} blocked={loading} onBegin={beginCommand} onEnd={endCommand} onError={message=>onLog('error',message)}/>
            </>
          )}

          {!browserOpen&&<BrowserProfileSelect disabled={loading}/>}
          {/* 浏览器控制 */}
          <div className="flex gap-2">
            {!browserOpen ? (
              <Button
                onClick={handleOpenBrowser}
                disabled={loading}
                loading={loading}
                variant="success"
                className="flex-1"
                size="lg"
              >
                {!loading && <Globe className="w-4 h-4" />}
                {loading ? '正在打开浏览器…' : '打开浏览器'}
              </Button>
            ) : (
              <>
                <Button variant="destructive" className="flex-1" onClick={handleCloseBrowser} disabled={loading} size="lg">
                  <X className="w-4 h-4" />
                  关闭浏览器
                </Button>
                <Button variant="tonal" onClick={checkStatus} disabled={loading} size="lg" title="刷新状态">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </>
            )}
          </div>

          {/* 元素选择器 */}
          {browserOpen && (
            <div className="section-block">
              <div className="section-block-header">
                <div className="icon-chip icon-chip-info !w-6 !h-6">
                  <MousePointer className="w-3.5 h-3.5" />
                </div>
                <span className="flex-1">元素选择器</span>
                {pickerActive ? (
                  <Button variant="destructive" size="sm" onClick={handleStopPicker} disabled={loading}>
                    停止选择
                  </Button>
                ) : (
                  <Button variant="info" size="sm" onClick={handleStartPicker} disabled={loading}>
                    <MousePointer className="w-3.5 h-3.5" />
                    启动选择器
                  </Button>
                )}
              </div>

              <div className="section-block-body !py-3 space-y-3">
                {pickerActive && (
                  <div className="status-row status-row-warning !items-start !py-2.5 flex-col gap-1.5">
                    <p className="font-semibold text-[12px]">选择器已激活，回到浏览器操作</p>
                    <ul className="text-[11px] space-y-1 mt-1 w-full">
                      <li className="flex items-center gap-1">
                        <kbd className="px-1.5 py-0.5 bg-[hsl(var(--card))] border border-[hsl(var(--warning-500)/0.4)] rounded font-mono text-[10px]">Ctrl</kbd>
                        <span>+ 点击：选择单个元素</span>
                      </li>
                      <li className="flex items-center gap-1">
                        <kbd className="px-1.5 py-0.5 bg-[hsl(var(--card))] border border-[hsl(var(--warning-500)/0.4)] rounded font-mono text-[10px]">Alt</kbd>
                        <span>依次点击两个相似元素，自动识别全部</span>
                      </li>
                      <li className="flex items-center gap-1">
                        <kbd className="px-1.5 py-0.5 bg-[hsl(var(--card))] border border-[hsl(var(--warning-500)/0.4)] rounded font-mono text-[10px]">Esc</kbd>
                        <span>取消选择</span>
                      </li>
                    </ul>
                  </div>
                )}

                {lastSelector && (
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">最近复制</label>
                    <div className="flex items-center gap-2 mt-1.5 p-2.5 bg-[hsl(var(--brand-50))] rounded-control border border-[hsl(var(--brand-500)/0.3)]">
                      <code className="flex-1 text-[12px] text-[hsl(var(--brand-700))] truncate font-mono" title={lastSelector}>
                        {lastSelector}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => copyToClipboard(lastSelector)}
                        title={copied ? '已复制' : '复制'}
                      >
                        {copied ? <Check className="w-3 h-3 text-[hsl(var(--success-600))]" /> : <Copy className="w-3 h-3" />}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 底部 */}
        <div className="dialog-footer-bar">
          <Button variant="secondary" size="sm" onClick={onClose}>
            关闭
          </Button>
        </div>
      </div>
    </div>

    {/* 缺少功能模块包时的安装引导（与「运行前预检」复用同一弹窗，提示内容一致） */}
    <MissingPacksDialog
      open={!!missingPacks}
      missing={missingPacks || []}
      onClose={() => setMissingPacks(null)}
      onOpenManager={() => { setMissingPacks(null); setShowFeaturePacks(true) }}
    />
    <FeaturePackDialog open={showFeaturePacks} onClose={() => setShowFeaturePacks(false)} />
    </DialogPortal>
  )
}
