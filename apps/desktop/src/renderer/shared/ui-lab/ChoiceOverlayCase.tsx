import { Select } from '../components/ui/select'
import { ScrollArea } from '../components/ui/scroll-area'
import { useState } from 'react'
import { Button } from '../components/ui/button'
import { Dialog, DialogTrigger, DialogContent, DialogTitle, DialogDescription, DialogClose } from '../components/ui/dialog'
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel } from '../components/ui/alert-dialog'
import { LabCombobox } from './LabCombobox'
import { kernelOptions, longOption } from './fixtures'

export function ChoiceOverlayCase() {
  const [selected, setSelected] = useState<string | null>('kernel-1')
  const [channel, setChannel] = useState<string | null>('stable')
  const [busy, setBusy] = useState(false)
  return <Dialog><DialogTrigger asChild><Button type="button" variant="primary">打开嵌套验证</Button></DialogTrigger>
    <DialogContent className="max-h-[90dvh] w-[min(94vw,44rem)] grid-rows-[auto_auto_minmax(0,1fr)_auto]">
      <DialogTitle>浏览器配置 · 验证</DialogTitle><DialogDescription>本地案例，不创建配置、不下载内核。</DialogDescription>
      <div className="min-h-0 overflow-y-auto p-1"><LabCombobox label="外层内核" value={selected} options={kernelOptions} onValueChange={setSelected} />
        <div className="mt-4 grid gap-2 text-sm"><span>弹窗内短选项</span><Select aria-label="弹窗内通道" value={channel} onValueChange={setChannel} options={[{ value: 'stable', label: 'Stable' }, { value: 'preview', label: 'Preview' }]} /></div>
        <p className="my-4 text-sm text-muted">内核窗口关闭后，焦点应回到管理内核按钮。</p>
        <Dialog busy={busy}><DialogTrigger asChild><Button type="button">管理内核 · 验证</Button></DialogTrigger>
          <DialogContent className="max-h-[85dvh] w-[min(92vw,40rem)] grid-rows-[auto_auto_minmax(0,1fr)_auto]">
            <DialogTitle>内核管理 · 验证</DialogTitle><DialogDescription>500 项目录、局部滚动、嵌套确认与忙状态。</DialogDescription>
            <div className="min-h-0 overflow-y-auto p-1" aria-label="内核滚动内容" tabIndex={0}>
              <LabCombobox label="内层内核" value={selected} options={[...kernelOptions, longOption]} onValueChange={setSelected} />
              <p role="status" className="my-3 text-sm text-muted">当前选择：{selected ?? '未选择'}</p>
              <ScrollArea className="mt-4 h-32 rounded-control border border-line bg-surface-subtle text-xs text-muted" viewportClassName="p-3" aria-label="滚动样本">
                {Array.from({ length: 30 }, (_, i) => <p key={i} className="whitespace-nowrap py-1">{i + 1}. 验证本机滚动条 · {'长内容 '.repeat(24)}</p>)}
              </ScrollArea>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" aria-pressed={busy} onClick={() => setBusy(!busy)}>{busy ? '结束忙状态' : '模拟忙状态'}</Button>
              <AlertDialog><AlertDialogTrigger asChild><Button type="button" variant="danger" disabled={busy}>打开删除确认</Button></AlertDialogTrigger>
                <AlertDialogContent><AlertDialogTitle>删除内核 · 验证</AlertDialogTitle><AlertDialogDescription>这里只检验第三层弹窗与默认取消焦点，不删除任何文件。</AlertDialogDescription>
                  <AlertDialogCancel asChild><Button type="button">取消删除</Button></AlertDialogCancel>
                </AlertDialogContent>
              </AlertDialog>
              <DialogClose asChild><Button type="button" disabled={busy}>关闭内核验证</Button></DialogClose>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <DialogClose asChild><Button type="button">关闭配置验证</Button></DialogClose>
    </DialogContent>
  </Dialog>
}
