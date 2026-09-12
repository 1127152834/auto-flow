import { CheckCircle, WarningCircle } from '@phosphor-icons/react'

export type ModelFeedback = { tone: 'success' | 'danger'; title: string; detail: string }

export function FeedbackCard({ feedback }: { feedback: ModelFeedback }) {
  const success = feedback.tone === 'success'
  const Icon = success ? CheckCircle : WarningCircle
  return <div role={success ? 'status' : 'alert'} className={`flex items-start gap-3 rounded-control border p-4 text-sm ${success ? 'border-sage/30 bg-sage-soft text-sage-strong' : 'border-danger/30 bg-danger-soft text-danger'}`}>
    <Icon size={20} className="mt-0.5 shrink-0" />
    <div className="min-w-0"><p className="m-0 font-semibold">{feedback.title}</p><p className="mb-0 mt-1 break-words">{feedback.detail}</p></div>
  </div>
}
