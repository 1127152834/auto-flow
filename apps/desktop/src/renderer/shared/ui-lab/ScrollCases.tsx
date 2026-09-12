import { ScrollArea } from '../components/ui/scroll-area'
export function ScrollCases() {
  return <section aria-labelledby="scroll-title" className="grid gap-4 rounded-card border border-line bg-surface p-6"><div><h2 id="scroll-title" className="font-semibold">双轴滚动容器</h2><p className="mt-1 text-xs text-muted">A07 · 溢出时常显，12px 操作轨道 / 6px 滑块；键盘、滚轮与拖动</p></div>
    <ScrollArea aria-label="双轴滚动验收" className="h-48 w-full rounded-control border border-line" viewportClassName="overscroll-contain"><ol className="w-[1600px] p-3 text-sm">{Array.from({ length: 40 }, (_, i) => <li key={i} className="py-2">{i + 1}. {'长内容 · 可复制的日志字段 / '.repeat(12)}</li>)}</ol></ScrollArea>
    <ScrollArea aria-label="无溢出滚动验收" className="h-20 rounded-control border border-line"><p className="p-3 text-sm">无溢出时不显示轨道。</p></ScrollArea>
  </section>
}
