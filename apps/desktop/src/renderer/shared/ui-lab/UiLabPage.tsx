import { ChoiceCases } from './ChoiceCases'
import { ScrollCases } from './ScrollCases'
import { SquaresFour } from '@phosphor-icons/react'
import { useState } from 'react'
import { ChoiceOverlayCase } from './ChoiceOverlayCase'
import { FormFocusCase } from './FormFocusCase'
import { ToggleCases } from './ToggleCases'
import { TextControlCases } from './TextControlCases'

const palette = ['canvas', 'surface', 'clay', 'clay-soft', 'control-border', 'ink', 'muted', 'danger', 'success', 'warning']
export function UiLabPage() {
  const [compact, setCompact] = useState(false)
  return <main data-ui-lab="autoflow-ui-controls-lab" className="mx-auto max-w-6xl space-y-6 px-6 py-8 text-ink">
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-6">
      <div className="flex gap-3"><span className="grid h-12 w-12 place-items-center rounded-card bg-clay text-on-accent"><SquaresFour size={28} /></span>
        <div><p className="text-xs font-semibold uppercase tracking-widest text-clay">Design system · G0</p><h1 className="text-2xl font-semibold">AutoFlow 控件实验室</h1></div></div>
      <span className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-muted">开发环境 · T0–T5 验证</span>
    </header>
    <p className="max-w-3xl text-sm leading-6 text-muted">先验证设计令牌、表单焦点和嵌套浮层。这里使用本地样本，不连接业务账户。完整组件展示与真实页面迁移在后续阶段进行。</p>
    <section className="grid gap-5 rounded-card border border-line bg-surface p-6" aria-labelledby="tokens-title">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="tokens-title" className="font-semibold">颜色与密度</h2><p className="mt-1 text-xs text-muted">A02 · 暖灰背景，黏土棕强调，清晰控件边界</p></div>
        <button type="button" aria-pressed={compact} onClick={() => setCompact(!compact)} className="rounded-control border border-control-border px-3 py-2 text-sm hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay">{compact ? '紧凑 32px' : '默认 40px'}</button></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">{palette.map(name => <div key={name} className="overflow-hidden rounded-control border border-line"><div data-token-swatch={name} className="h-12" style={{ backgroundColor: `var(--color-${name})` }} /><p className="px-2 py-2 font-mono text-xs">{name}</p></div>)}</div>
      <div className="grid gap-4 sm:grid-cols-3">{[{ title: '常规输入', props: { placeholder: '中文 / English' } }, { title: '只读输入', props: { readOnly: true, defaultValue: '可选择和复制' } }, { title: '禁用输入', props: { disabled: true, defaultValue: '操作暂不可用' } }].map(({ title, props }) => <label key={title} className="grid gap-2 text-sm">{title}<input data-af-control className="min-w-0 px-3 text-sm" style={{ height: `var(--control-${compact ? 'sm' : 'md'})` }} {...props} /></label>)}</div>
    </section>
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <section className="grid gap-4 rounded-card border border-line bg-surface p-6" aria-labelledby="focus-title"><div><h2 id="focus-title" className="font-semibold">表单绑定与错误聚焦</h2><p className="mt-1 text-xs text-muted">A03 / A04 · RHF、500项选择、reset与dirty</p></div><FormFocusCase /></section>
      <section className="grid gap-4 rounded-card border border-line bg-surface p-6" aria-labelledby="overlay-title"><div><h2 id="overlay-title" className="font-semibold">嵌套弹窗与滚动</h2><p className="mt-1 text-xs text-muted">A06 / A07 · 三层模态窗口与内部选项浮层</p></div><p className="text-sm leading-6 text-muted">依次打开配置、内核管理、删除确认。先展开下拉再按 Escape，应只收起下拉；忙状态中应阻止关闭窗口。</p><ChoiceOverlayCase /></section>
    </div>
    <TextControlCases size={compact ? 'sm' : 'md'} />
    <ToggleCases />
    <ChoiceCases size={compact ? 'sm' : 'md'} />
    <ScrollCases />
    <footer className="text-xs leading-6 text-muted">本页仅辅助验收。后续仍须覆盖浏览器、代理、模型、设置与总览的真实应用流程；Windows 与读屏验收未执行。</footer>
  </main>
}
