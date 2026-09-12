import { createContext, useContext, useState, type CSSProperties } from 'react'

type OverlayScope = { depth: number; container: HTMLElement | null }
export const OverlayHostContext = createContext<OverlayScope>({ depth: -1, container: null })

export function useOverlayFrame() {
  const parent = useContext(OverlayHostContext)
  const [container, setContainer] = useState<HTMLElement | null>(null)
  const depth = parent.depth + 1
  return {
    scope: { depth, container },
    hostRef: setContainer,
    // Radix listens in document capture; let the owned popup process Escape
    // before the modal dismisses. The popup still owns its keyboard behavior.
    hasOpenPopup: () => Boolean(container?.querySelector('[data-af-popup]:not([data-exiting])')),
    overlayStyle: { zIndex: `calc(var(--layer-modal) + ${depth} * var(--layer-step))` } satisfies CSSProperties,
    contentStyle: { zIndex: `calc(var(--layer-modal) + ${depth} * var(--layer-step) + 1)` } satisfies CSSProperties,
  }
}

export function useOverlayHost() {
  const scope = useContext(OverlayHostContext)
  return {
    container: scope.container ?? undefined,
    style: { zIndex: scope.depth < 0 ? 'var(--layer-popup)' : `calc(var(--layer-modal) + ${scope.depth} * var(--layer-step) + 2)` } satisfies CSSProperties,
  }
}
