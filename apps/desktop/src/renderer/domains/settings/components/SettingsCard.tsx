import type { Icon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

export function SettingsCard({ icon: Icon, title, description, action, children }: { icon: Icon; title: string; description?: string; action?: ReactNode; children?: ReactNode }) {
  return <section className="rounded-card border border-line bg-surface p-6 shadow-sm">
    <header className="flex flex-wrap items-start gap-4 border-b border-line pb-5">
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-surface-subtle"><Icon size={23} weight="duotone" /></span>
      <div className="min-w-0 flex-1"><h2 className="m-0 text-xl font-semibold">{title}</h2>{description ? <p className="mb-0 mt-1 text-sm text-muted">{description}</p> : null}</div>
      {action}
    </header>
    {children ? <div className="pt-5">{children}</div> : null}
  </section>
}

export function DetailGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return <dl className="m-0 grid gap-4 sm:grid-cols-2">{items.map(({ label, value }) => <div key={label} className="border-l border-line pl-4 first:border-l-0 first:pl-0"><dt className="text-sm text-muted">{label}</dt><dd className="m-0 mt-1 break-all font-medium">{value}</dd></div>)}</dl>
}
