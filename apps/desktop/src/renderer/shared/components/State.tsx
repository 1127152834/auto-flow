import { EmptyState } from './ui/empty-state'
import type { ReactNode } from 'react'

type StateProps = {
  title: string
  description?: string
  action?: ReactNode
}

export function State({ title, description, action }: StateProps) {
  return <EmptyState title={title} description={description} action={action} />
}
