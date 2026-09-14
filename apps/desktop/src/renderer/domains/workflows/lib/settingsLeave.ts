type CloseHandler = () => Promise<boolean>
let handler: CloseHandler | undefined

/** The mounted settings owner confirms closure after resolving its draft. */
export function registerSettingsCloseHandler(next: CloseHandler): () => void {
  handler = next
  return () => { if (handler === next) handler = undefined }
}
export async function requestSettingsClose(): Promise<boolean> {
  return handler ? handler() : false
}

export const hasSettingsCloseHandler=()=>handler!==undefined
