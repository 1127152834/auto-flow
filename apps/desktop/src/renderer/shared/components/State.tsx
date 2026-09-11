import type { ReactNode } from 'react'

type StateProps = {
  title: string
  description?: string
  action?: ReactNode
}

export function State({ title, description, action }: StateProps) {
  return (
    <section className="state" role="status" aria-live="polite">
      <h1>{title}</h1>
      {description ? <p>{description}</p> : null}
      {action ? <div className="state__action">{action}</div> : null}
    </section>
  )
}
