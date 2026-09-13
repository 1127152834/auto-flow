import type { ReactNode } from 'react'

export type DataTablePageFrameProps = {
  header: ReactNode
  tabs: ReactNode
  notice: ReactNode
  children: ReactNode
  footer?: ReactNode
}

export function DataTablePageFrame({ header, tabs, notice, children, footer }: DataTablePageFrameProps) {
  return <section data-testid="data-table-page-frame" data-table-page-frame className="min-w-0 overflow-hidden rounded-card border border-line bg-surface">
    <div data-table-page-frame-header className="flex min-w-0 w-full flex-wrap items-start justify-between gap-x-8 gap-y-4 px-5 pt-5">
      <div className="min-w-0 flex-1">{header}</div>
      <div className="min-w-0 max-w-full overflow-x-auto">{tabs}</div>
    </div>
    {notice ? <div className="px-5 pt-4">{notice}</div> : null}
    <div className="min-w-0 p-5">{children}</div>
    {footer ? <footer className="w-full border-t border-line px-5 py-3">{footer}</footer> : null}
  </section>
}
