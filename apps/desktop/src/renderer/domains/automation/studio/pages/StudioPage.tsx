import { useMemo, useState } from 'react'
import { BracketsCurly, CaretDown, CheckCircle, CircleNotch, Globe, Lightning, MagnifyingGlass, Mouse, Play, Plus, TextAa, Timer } from '@phosphor-icons/react'
import { Button } from '../../../../shared/components/ui/button'
import { Input } from '../../../../shared/components/ui/input'

type NodeKind = 'open_page' | 'click_element' | 'input_text' | 'wait' | 'get_element_info'
type Icon = typeof Globe
type CatalogItem = { type: NodeKind; title: string; detail: string; icon: Icon }
type StudioNode = { id: string; type: NodeKind; title: string; summary: string; icon: Icon; tone: string }

const nodeCatalog: CatalogItem[] = [
  { type: 'open_page', title: '打开网页', detail: '导航到一个页面', icon: Globe },
  { type: 'click_element', title: '点击元素', detail: '点击、双击或右键', icon: Mouse },
  { type: 'input_text', title: '输入文本', detail: '填充输入框内容', icon: TextAa },
  { type: 'wait', title: '等待', detail: '等待时间或页面状态', icon: Timer },
  { type: 'get_element_info', title: '读取元素', detail: '读取文本或属性', icon: BracketsCurly },
]

const initialNodes: StudioNode[] = [
  { id: 'node-1', type: 'open_page', title: '打开网页', summary: 'https://example.com', icon: Globe, tone: 'text-sage-strong' },
  { id: 'node-2', type: 'click_element', title: '点击元素', summary: '#start', icon: Mouse, tone: 'text-clay' },
  { id: 'node-3', type: 'input_text', title: '输入文本', summary: 'selector · 未配置', icon: TextAa, tone: 'text-clay' },
]

export function StudioPage() {
  const [query, setQuery] = useState('')
  const [nodes, setNodes] = useState(initialNodes)
  const [selectedId, setSelectedId] = useState(initialNodes[1].id)
  const [running, setRunning] = useState(false)
  const selected = nodes.find((node) => node.id === selectedId) ?? nodes[0]
  const filteredCatalog = useMemo(() => nodeCatalog.filter((item) => item.title.includes(query.trim()) || item.type.includes(query.trim())), [query])

  function addNode(type: NodeKind) {
    const definition = nodeCatalog.find((item) => item.type === type)!
    const id = `node-${nodes.length + 1}`
    const next: StudioNode = { id, type, title: definition.title, summary: summaryFor(type), icon: definition.icon, tone: type === 'open_page' ? 'text-sage-strong' : 'text-clay' }
    setNodes((current) => [...current, next])
    setSelectedId(id)
  }

  return <div className="flex min-h-[calc(100dvh-74px)] min-w-0 flex-col bg-[#e9e6df] text-ink">
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <div className="flex min-w-0 items-center gap-4"><div className="flex items-center gap-2"><Lightning size={18} weight="fill" className="text-clay" /><span className="text-sm font-bold">自动化工作台</span></div><span className="h-5 w-px bg-line" /><button type="button" className="flex items-center gap-2 rounded-control px-2 py-1.5 text-sm font-semibold hover:bg-surface-hover"><span>未命名自动化</span><CaretDown size={15} className="text-muted" /></button></div>
      <div className="flex items-center gap-2"><span className="mr-2 text-xs text-muted">编辑中 · 未保存</span><Button variant="ghost" onClick={() => setRunning(false)}>保存</Button><Button variant="primary" onClick={() => setRunning(true)}><Play size={16} weight="fill" />{running ? '运行中' : '运行'}</Button></div>
    </header>
    <div className="grid min-h-0 flex-1 grid-cols-[268px_minmax(0,1fr)_320px]">
      <aside className="min-h-0 border-r border-line bg-surface px-4 py-5" aria-label="模块目录">
        <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-clay">节点目录</p><h2 className="mt-1 text-base font-bold">网页自动化</h2></div><button type="button" className="rounded-control p-2 text-muted hover:bg-surface-hover hover:text-ink" aria-label="添加节点"><Plus size={18} /></button></div>
        <label className="relative mt-5 block"><MagnifyingGlass size={17} className="absolute left-3 top-2.5 text-muted" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索节点" className="w-full pl-9" /></label>
        <div className="mt-5 space-y-2">{filteredCatalog.map((item) => { const Icon = item.icon; return <button key={item.type} type="button" onClick={() => addNode(item.type)} className="flex w-full items-center gap-3 rounded-control border border-transparent px-3 py-3 text-left transition-colors hover:border-line hover:bg-surface-hover"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-clay-soft text-clay"><Icon size={17} weight="duotone" /></span><span className="min-w-0"><strong className="block text-sm font-semibold">{item.title}</strong><small className="mt-0.5 block truncate text-xs text-muted">{item.detail}</small></span></button> })}</div>
        <div className="mt-7 border-t border-line pt-4"><p className="text-xs leading-5 text-muted">点击节点即可加入流程。更多模块将在 Studio 基础能力稳定后逐批开放。</p></div>
      </aside>
      <main className="relative min-h-0 overflow-hidden bg-[#eeeae2]" aria-label="工作流画布">
        <div className="absolute inset-0 opacity-60" style={{ backgroundImage: 'radial-gradient(#c9c4ba 0.8px, transparent 0.8px)', backgroundSize: '20px 20px' }} />
        <div className="relative flex h-full min-h-[620px] flex-col"><div className="flex items-center justify-between border-b border-line/70 bg-[#eeeae2]/80 px-5 py-3 backdrop-blur-sm"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">流程画布</p><p className="mt-1 text-xs text-muted">{nodes.length} 个节点 · 当前编辑会话</p></div><div className="flex items-center gap-2 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-sage" />准备运行</div></div>
          <div className="relative mx-auto flex w-full max-w-[680px] flex-1 flex-col items-stretch px-10 py-14">{nodes.map((node, index) => { const Icon = node.icon; return <div key={node.id} className="relative flex items-center"><button type="button" onClick={() => setSelectedId(node.id)} className={`group flex w-full items-center gap-4 rounded-card border bg-surface px-4 py-4 text-left shadow-[0_7px_22px_rgba(69,62,52,0.06)] transition-all hover:-translate-y-px ${selectedId === node.id ? 'border-clay ring-2 ring-clay/15' : 'border-line'}`}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-surface-subtle ${node.tone}`}><Icon size={20} weight="duotone" /></span><span className="min-w-0 flex-1"><span className="flex items-center gap-2"><strong className="text-sm font-bold">{node.title}</strong><code className="text-[10px] text-muted">{node.type}</code></span><span className="mt-1 block truncate text-xs text-muted">{node.summary}</span></span><span className="text-xs text-muted">{index + 1}</span></button>{index < nodes.length - 1 && <span className="absolute left-[33px] top-full h-14 w-px bg-line-strong" />}</div> })}<button type="button" onClick={() => addNode('wait')} className="mt-14 flex items-center justify-center gap-2 rounded-card border border-dashed border-line-strong bg-surface/50 px-4 py-4 text-sm font-semibold text-muted hover:border-clay hover:text-clay"><Plus size={18} />添加下一个节点</button></div>
          <div className="flex items-center justify-between border-t border-line/70 bg-surface/60 px-5 py-2.5 text-xs text-muted"><span>滚轮缩放 · 拖动画布 · 点击节点编辑</span><span>100%</span></div>
        </div>
      </main>
      <aside className="min-h-0 overflow-auto border-l border-line bg-surface px-5 py-5" aria-label="节点配置"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-clay">节点配置</p><h2 className="mt-1 text-lg font-bold">{selected.title}</h2></div><span className="rounded-full bg-sage-soft px-2.5 py-1 text-[11px] font-semibold text-sage-strong">已选择</span></div><div className="mt-6 space-y-5">{selected.type === 'open_page' && <EditorField label="网址"><Input defaultValue="https://example.com" /></EditorField>}{selected.type !== 'open_page' && <EditorField label="选择器"><Input defaultValue={selected.type === 'click_element' ? '#start' : ''} placeholder="#login-button 或 //button" /></EditorField>}{selected.type === 'input_text' && <EditorField label="输入内容"><Input placeholder="支持变量引用，例如 {username}" /></EditorField>}{selected.type === 'get_element_info' && <EditorField label="读取属性"><select defaultValue="text" className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm outline-none focus:border-clay"><option value="text">文本内容</option><option value="value">输入值</option><option value="href">href</option><option value="attribute">自定义属性</option></select></EditorField>}{selected.type === 'wait' && <EditorField label="等待秒数"><Input defaultValue="1" /></EditorField>}<EditorField label="超时（秒）"><Input defaultValue="30" /></EditorField></div><div className="mt-8 rounded-card border border-line bg-surface-subtle p-4"><div className="flex items-start gap-3"><CheckCircle size={18} weight="fill" className="mt-0.5 text-sage-strong" /><div><p className="text-sm font-semibold">配置已通过基础检查</p><p className="mt-1 text-xs leading-5 text-muted">真实执行将在 CloakBrowser 运行时接通后启用。</p></div></div></div><div className="mt-6 border-t border-line pt-5"><p className="text-xs font-semibold text-muted">输出</p><div className="mt-3 flex items-center gap-2 text-sm"><BracketsCurly size={17} className="text-clay" /><span>暂不产生输出变量</span></div></div></aside>
    </div>
    {running && <div className="fixed bottom-5 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full border border-line bg-surface px-4 py-2.5 text-sm shadow-[0_10px_30px_rgba(69,62,52,0.14)]"><CircleNotch size={17} className="animate-spin text-clay" /><span>模拟运行已开始</span><button type="button" onClick={() => setRunning(false)} className="font-semibold text-clay hover:text-clay-strong">停止</button></div>}
  </div>
}

function summaryFor(type: NodeKind) { return type === 'open_page' ? 'https://example.com' : type === 'wait' ? '等待 1 秒' : `${type} · 未配置` }
function EditorField({ label, children }: { label: string; children: React.ReactNode }) { return <label className="grid gap-2 text-sm"><span className="font-semibold">{label}</span>{children}</label> }
