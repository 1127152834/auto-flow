// Source: WebRPA@5ccb900e, components/workflow/ScreenshotNameDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState } from 'react'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { X, Image as ImageIcon, AlertCircle, RotateCcw, Info } from 'lucide-react'
import { DialogPortal } from './controls/dialog-portal'

interface ScreenshotNameDialogProps {
  defaultName: string
  onConfirm: (name: string) => void
  onCancel: () => void
  onRetry?: () => void
}

export function ScreenshotNameDialog({
  defaultName,
  onConfirm,
  onCancel,
  onRetry: _onRetry
}: ScreenshotNameDialogProps) {
  const [name, setName] = useState(defaultName.replace('.png', ''))

  const handleConfirm = () => {
    if (name.trim()) {
      onConfirm(name.trim())
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirm()
    } else if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <DialogPortal>
    <div
      className="fixed inset-0 flex items-center justify-center bg-[hsl(217_45%_15%_/_0.55)] backdrop-blur-[3px] p-4 animate-fade-in"
      style={{ zIndex: 2147483640 }}
    >
      <div className="modern-dialog w-full max-w-[460px] animate-scale-in-bounce">
        {/* 标题栏 */}
        <div className="modern-dialog-header">
          <div className="modern-dialog-header-icon modern-dialog-header-icon-success">
            <ImageIcon className="w-5 h-5" strokeWidth={2.2} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="modern-dialog-title">截图成功</h2>
            <div className="modern-dialog-subtitle">为这张截图取个好记的名字</div>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-[7px] text-[hsl(var(--slate-500))] hover:bg-[hsl(var(--danger-50))] hover:text-[hsl(var(--danger-600))] hover:border-[hsl(var(--danger-500)/0.3)] border border-transparent transition-all duration-150 active:scale-90"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容区 */}
        <div className="px-5 py-4 space-y-3">
          <div className="space-y-1.5">
            <label className="text-[12px] font-semibold text-[hsl(var(--slate-800))]">
              截图名称
              <span className="ml-1.5 text-[10.5px] font-normal text-[hsl(var(--muted-foreground))]">不含扩展名</span>
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入截图名称"
              autoFocus
            />
            <div className="flex items-center gap-1.5 pl-0.5 text-[11px] text-[hsl(var(--muted-foreground))]">
              <span>保存为：</span>
              <code className="px-1.5 py-0.5 rounded bg-[hsl(var(--brand-50))] border border-[hsl(var(--brand-500)/0.25)] text-[hsl(var(--brand-700))] font-mono">
                {name.trim() || '未命名'}.png
              </code>
            </div>
          </div>

          <div className="status-row status-row-info !py-2">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[12px]">
              已保存到图像资源，可在底部面板的「图像资源」标签查看
            </span>
          </div>
        </div>

        {/* 按钮栏 */}
        <div className="dialog-footer-bar">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            取消
          </Button>
          <Button variant="success" size="sm" onClick={handleConfirm} disabled={!name.trim()}>
            保存截图
          </Button>
        </div>
      </div>
    </div>
    </DialogPortal>
  )
}

interface ScreenshotErrorDialogProps {
  error: string
  cancelled?: boolean
  onRetry: () => void
  onCancel: () => void
}

export function ScreenshotErrorDialog({
  error,
  cancelled,
  onRetry,
  onCancel
}: ScreenshotErrorDialogProps) {
  const [retrying, setRetrying] = useState(false)

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await new Promise(resolve => setTimeout(resolve, 500))
      onRetry()
    } finally {
      setRetrying(false)
    }
  }

  return (
    <DialogPortal>
    <div
      className="fixed inset-0 flex items-center justify-center bg-[hsl(217_45%_15%_/_0.55)] backdrop-blur-[3px] p-4 animate-fade-in"
      style={{ zIndex: 2147483640 }}
    >
      <div className="modern-dialog w-full max-w-[480px] animate-scale-in-bounce">
        {/* 标题栏 */}
        <div className="modern-dialog-header">
          <div className="modern-dialog-header-icon modern-dialog-header-icon-danger">
            <AlertCircle className="w-5 h-5" strokeWidth={2.2} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="modern-dialog-title">截图失败</h2>
            <div className="modern-dialog-subtitle">
              {cancelled ? '您取消了截图操作' : '截图过程中出现问题'}
            </div>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-[7px] text-[hsl(var(--slate-500))] hover:bg-[hsl(var(--danger-50))] hover:text-[hsl(var(--danger-600))] hover:border-[hsl(var(--danger-500)/0.3)] border border-transparent transition-all duration-150 active:scale-90"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容区 */}
        <div className="px-5 py-4 space-y-3">
          <div className="status-row status-row-danger !items-start !py-2.5 flex-col gap-1">
            <p className="text-[11.5px] font-semibold uppercase tracking-wider w-full">错误信息</p>
            <p className="text-[12px] font-mono break-words leading-relaxed w-full">
              {error === 'timeout'
                ? '等待超时（90 秒） — 您可能没有完成截图，或截图工具未正确启动'
                : error}
            </p>
          </div>

          <div className="section-block">
            <div className="section-block-header">
              <div className="icon-chip icon-chip-info !w-6 !h-6">
                <Info className="w-3.5 h-3.5" />
              </div>
              故障排查
            </div>
            <div className="section-block-body !py-3">
              <ul className="space-y-1.5 text-[12px] text-[hsl(var(--slate-700))]">
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>确保 Windows 截图工具已启用</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>尝试手动按 <kbd className="px-1.5 py-0.5 bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded text-[10px] font-mono shadow-xs">Win+Shift+S</kbd> 测试</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-[hsl(var(--brand-600))] mt-0.5">•</span>
                  <span>若仍失败，请点击右下角「重试截图」</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* 按钮栏 */}
        <div className="dialog-footer-bar">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            关闭
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleRetry}
            disabled={retrying}
            loading={retrying}
          >
            {!retrying && <RotateCcw className="w-3.5 h-3.5" />}
            {retrying ? '重试中...' : '重试截图'}
          </Button>
        </div>
      </div>
    </div>
    </DialogPortal>
  )
}
