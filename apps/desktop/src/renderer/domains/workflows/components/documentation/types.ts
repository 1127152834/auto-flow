// Source: WebRPA@5ccb900e, components/workflow/documentation/types.ts; see SOURCE.md for license and adaptation boundaries.
import type { LucideIcon } from 'lucide-react'

export interface DocumentItem {
  id: string
  title: string
  icon: LucideIcon
  description: string
}

export interface DocumentationDialogProps {
  isOpen: boolean
  onClose: () => void
}
