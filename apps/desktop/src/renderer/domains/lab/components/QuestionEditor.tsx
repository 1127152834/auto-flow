import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import type { QuestionDraft } from '../types'

export function QuestionEditor({ drafts, onChange }: { drafts: QuestionDraft[]; onChange(value: QuestionDraft[]): void }) {
  const change = (index: number, next: QuestionDraft) => onChange(drafts.map((item, at) => at === index ? next : item))
  const add = () => {
    let number = drafts.length + 1
    while (drafts.some(item => item.id === `question_${number}`)) number++
    onChange([...drafts, { id: `question_${number}`, type: 'noul', instructions: '', options: [], levels: [] }])
  }
  return <section className="grid gap-4" aria-labelledby="lab-questions-heading">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="lab-questions-heading" className="m-0 text-lg font-semibold">判断问题</h2><p className="m-0 mt-1 text-sm text-muted">一次最多提出 8 个问题，模型会在同一次推理中回答。</p></div><Button size="sm" onClick={add} disabled={drafts.length >= 8}>添加问题</Button></div>
    {drafts.map((draft, index) => <div key={index} className="grid gap-3 rounded-control border border-line bg-surface-subtle p-4">
      <div className="flex items-center justify-between"><strong className="text-sm">问题 {index + 1}</strong><Button size="sm" variant="ghost" onClick={() => onChange(drafts.filter((_, at) => at !== index))}>移除</Button></div>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
        <label className="grid gap-1 text-sm font-medium" htmlFor={`lab-question-id-${index}`}>问题 ID<Input id={`lab-question-id-${index}`} value={draft.id} maxLength={40} onChange={event => change(index, { ...draft, id: event.target.value })} /></label>
        <div className="grid gap-1 text-sm font-medium"><label htmlFor={`lab-question-type-${index}`}>类型</label><Select id={`lab-question-type-${index}`} value={draft.type} clearable={false} options={[{ value: 'choice', label: 'choice · 分类' }, { value: 'score', label: 'score · 评分' }, { value: 'noul', label: 'noul · 判断' }]} onValueChange={value => { if (value === 'choice' || value === 'score' || value === 'noul') change(index, { ...draft, type: value, options: draft.options.length ? draft.options : [{ key: 'yes', description: 'Yes' }, { key: 'no', description: 'No' }], levels: draft.levels.length ? draft.levels : ['Low', 'High'] }) }} /></div>
      </div>
      <label className="grid gap-1 text-sm font-medium" htmlFor={`lab-question-instruction-${index}`}>问题说明<Input id={`lab-question-instruction-${index}`} value={draft.instructions} maxLength={256} placeholder="例如：哪个团队应该处理这条消息？" onChange={event => change(index, { ...draft, instructions: event.target.value })} /></label>
      {draft.type === 'choice' ? <div className="grid gap-2"><span className="text-sm font-medium">候选项与说明</span>{draft.options.map((option, at) => <div key={at} className="grid gap-2 sm:grid-cols-[160px_minmax(0,1fr)_auto]">
        <Input aria-label={`问题 ${index + 1} 候选 ${at + 1} 键`} value={option.key} maxLength={40} placeholder="键" onChange={event => change(index, { ...draft, options: draft.options.map((item, i) => i === at ? { ...item, key: event.target.value } : item) })} />
        <Input aria-label={`问题 ${index + 1} 候选 ${at + 1} 说明`} value={option.description} maxLength={160} placeholder="这个选项适用的情况" onChange={event => change(index, { ...draft, options: draft.options.map((item, i) => i === at ? { ...item, description: event.target.value } : item) })} />
        <Button size="sm" variant="ghost" aria-label={`移除候选 ${at + 1}`} disabled={draft.options.length <= 2} onClick={() => change(index, { ...draft, options: draft.options.filter((_, i) => i !== at) })}>移除</Button>
      </div>)}<Button size="sm" className="justify-self-start" disabled={draft.options.length >= 10} onClick={() => change(index, { ...draft, options: [...draft.options, { key: `option_${draft.options.length + 1}`, description: '' }] })}>添加候选</Button></div> : null}
      {draft.type === 'score' ? <div className="grid gap-2"><span className="text-sm font-medium">评分等级（从低到高）</span>{draft.levels.map((level, at) => <div key={at} className="flex gap-2"><Input aria-label={`问题 ${index + 1} 等级 ${at + 1}`} value={level} maxLength={160} onChange={event => change(index, { ...draft, levels: draft.levels.map((item, i) => i === at ? event.target.value : item) })} /><Button size="sm" variant="ghost" aria-label={`移除等级 ${at + 1}`} disabled={draft.levels.length <= 2} onClick={() => change(index, { ...draft, levels: draft.levels.filter((_, i) => i !== at) })}>移除</Button></div>)}<Button size="sm" className="justify-self-start" disabled={draft.levels.length >= 10} onClick={() => change(index, { ...draft, levels: [...draft.levels, ''] })}>添加等级</Button></div> : null}
    </div>)}
  </section>
}
